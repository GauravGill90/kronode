"""Skill composition — merges multiple skills into a single runtime config.

Replaces the old get_profile() system. Loads an org's assigned skills from DB
and composes their prompts, extensions, dirs, and priorities.
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, AgentSkill

logger = logging.getLogger(__name__)


@dataclass
class ComposedSkillSet:
    system_prompt: str = ""
    allowed_extensions: frozenset[str] = field(default_factory=frozenset)
    allowed_dirs: list[str] = field(default_factory=list)
    context_priorities: list[str] = field(default_factory=list)
    skill_names: list[str] = field(default_factory=list)
    stack_chips: list[str] = field(default_factory=list)


async def compose_skills(org_id: int, db: AsyncSession) -> ComposedSkillSet:
    """Load an org's assigned skills and compose into a single skill set.

    Falls back to the old agent_profile column if no skills are assigned,
    auto-populating from the preset mapping.
    """
    # Load assigned skills in position order
    result = await db.execute(
        select(Skill)
        .join(AgentSkill, AgentSkill.skill_id == Skill.id)
        .where(AgentSkill.org_id == org_id)
        .order_by(AgentSkill.position)
    )
    skills = result.scalars().all()

    # Fallback: if no skills assigned, try to auto-populate from old agent_profile
    if not skills:
        skills = await _fallback_from_profile(org_id, db)

    if not skills:
        logger.warning(f"[SkillComposer] Org {org_id}: no skills assigned, using empty set")
        return ComposedSkillSet()

    # Compose
    prompts = []
    all_extensions: set[str] = set()
    all_dirs: list[str] = []
    all_priorities: list[str] = []
    all_names: list[str] = []
    all_chips: list[str] = []

    for skill in skills:
        if skill.system_prompt:
            prompts.append(skill.system_prompt)
        all_extensions.update(skill.allowed_extensions or [])
        for d in (skill.allowed_dirs or []):
            if d not in all_dirs:
                all_dirs.append(d)
        for p in (skill.context_priorities or []):
            if p not in all_priorities:
                all_priorities.append(p)
        all_names.append(skill.name)
        all_chips.extend(c for c in (skill.stack_chips or []) if c not in all_chips)

    composed = ComposedSkillSet(
        system_prompt="\n\n---\n\n".join(prompts),
        allowed_extensions=frozenset(all_extensions),
        allowed_dirs=all_dirs,
        context_priorities=all_priorities,
        skill_names=all_names,
        stack_chips=all_chips,
    )

    logger.info(f"[SkillComposer] Org {org_id}: composed {len(skills)} skills: {all_names}")
    return composed


async def _fallback_from_profile(org_id: int, db: AsyncSession) -> list:
    """If org has old agent_profile but no skills, auto-assign from preset mapping."""
    from app.models.org import OnboardingConfig
    from app.skills.presets import PRESETS

    config = (await db.execute(
        select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
    )).scalar_one_or_none()

    if not config or not config.agent_profile:
        return []

    profile_key = config.agent_profile
    skill_keys = PRESETS.get(profile_key, [])
    if not skill_keys:
        return []

    logger.info(f"[SkillComposer] Org {org_id}: auto-migrating profile '{profile_key}' to skills: {skill_keys}")

    # Load the skill rows
    result = await db.execute(
        select(Skill).where(Skill.key.in_(skill_keys))
    )
    skills = result.scalars().all()

    # Auto-assign them to the org
    for i, skill in enumerate(skills):
        existing = (await db.execute(
            select(AgentSkill).where(AgentSkill.org_id == org_id, AgentSkill.skill_id == skill.id)
        )).scalar_one_or_none()
        if not existing:
            db.add(AgentSkill(org_id=org_id, skill_id=skill.id, position=i))

    await db.commit()
    return skills
