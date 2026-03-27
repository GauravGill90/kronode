from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.skill import Skill, AgentSkill
from app.schemas.skill import (
    SkillOut, SkillDetailOut, SkillAssignPayload,
    SkillCreatePayload, SkillUpdatePayload,
)

router = APIRouter()


async def _get_org_id(user_data: dict, db: AsyncSession) -> int:
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    if not user or not user.org_id:
        raise HTTPException(status_code=400, detail="Onboarding not complete")
    return user.org_id


@router.get("/skills/")
async def list_skills(
    category: str | None = Query(None),
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse all available skills (global curated + org's custom)."""
    org_id = await _get_org_id(user_data, db)

    query = select(Skill).where(
        (Skill.org_id.is_(None)) | (Skill.org_id == org_id)
    )
    if category:
        query = query.where(Skill.category == category)
    query = query.order_by(Skill.category, Skill.name)

    result = await db.execute(query)
    skills = result.scalars().all()

    # Check which ones are assigned to this org
    assigned = (await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.org_id == org_id)
    )).scalars().all()
    assigned_set = set(assigned)

    return {
        "skills": [
            {
                **SkillOut.model_validate(s).model_dump(),
                "assigned": s.id in assigned_set,
            }
            for s in skills
        ]
    }


@router.get("/skills/presets")
async def list_presets(
    user_data: dict = Depends(get_current_user),
):
    """List preset bundles for quick setup."""
    from app.skills.presets import PRESETS
    return {"presets": {k: v for k, v in PRESETS.items()}}


@router.get("/onboarding/skills")
async def get_assigned_skills(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the org's currently assigned skills."""
    # Import the helper from onboarding to get or create org
    from app.api.v1.onboarding import _get_or_create_org
    _, org, _ = await _get_or_create_org(user_data, db)
    org_id = org.id

    result = await db.execute(
        select(Skill)
        .join(AgentSkill, AgentSkill.skill_id == Skill.id)
        .where(AgentSkill.org_id == org_id)
        .order_by(AgentSkill.position)
    )
    skills = result.scalars().all()

    return {
        "skills": [SkillOut.model_validate(s).model_dump() for s in skills]
    }


@router.post("/onboarding/skills")
async def save_assigned_skills(
    payload: SkillAssignPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the org's selected skills. Accepts skill_ids or a preset name."""
    # Import the helper from onboarding to get or create org
    from app.api.v1.onboarding import _get_or_create_org
    _, org, _ = await _get_or_create_org(user_data, db)
    org_id = org.id

    # Resolve preset to skill IDs if provided
    skill_ids = list(payload.skill_ids)
    if payload.preset and not skill_ids:
        from app.skills.presets import PRESETS
        skill_keys = PRESETS.get(payload.preset, [])
        if not skill_keys:
            raise HTTPException(status_code=400, detail=f"Unknown preset: {payload.preset}")
        result = await db.execute(select(Skill.id).where(Skill.key.in_(skill_keys)))
        skill_ids = list(result.scalars().all())

    if not skill_ids:
        raise HTTPException(status_code=400, detail="No skills selected")

    # Clear existing assignments
    existing = (await db.execute(
        select(AgentSkill).where(AgentSkill.org_id == org_id)
    )).scalars().all()
    for e in existing:
        await db.delete(e)

    # Assign new skills in order
    for i, sid in enumerate(skill_ids):
        db.add(AgentSkill(org_id=org_id, skill_id=sid, position=i))

    await db.commit()
    return {"ok": True, "assigned": len(skill_ids)}


@router.post("/skills/", status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillCreatePayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom skill (org-scoped)."""
    org_id = await _get_org_id(user_data, db)

    skill = Skill(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        stack_chips=payload.stack_chips,
        system_prompt=payload.system_prompt,
        allowed_extensions=payload.allowed_extensions,
        allowed_dirs=payload.allowed_dirs,
        context_priorities=payload.context_priorities,
        is_preset=False,
        org_id=org_id,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return SkillOut.model_validate(skill)


@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: int,
    payload: SkillUpdatePayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a custom skill. Only org-owned skills can be edited."""
    org_id = await _get_org_id(user_data, db)

    skill = (await db.execute(
        select(Skill).where(Skill.id == skill_id)
    )).scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.org_id != org_id:
        raise HTTPException(status_code=403, detail="Cannot edit a curated skill")

    for field in ("name", "description", "system_prompt", "allowed_extensions", "allowed_dirs", "context_priorities"):
        val = getattr(payload, field)
        if val is not None:
            setattr(skill, field, val)

    await db.commit()
    return {"ok": True}


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: int,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom skill. Only org-owned skills can be deleted."""
    org_id = await _get_org_id(user_data, db)

    skill = (await db.execute(
        select(Skill).where(Skill.id == skill_id)
    )).scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.org_id != org_id:
        raise HTTPException(status_code=403, detail="Cannot delete a curated skill")

    # Remove assignments first
    assignments = (await db.execute(
        select(AgentSkill).where(AgentSkill.skill_id == skill_id)
    )).scalars().all()
    for a in assignments:
        await db.delete(a)

    await db.delete(skill)
    await db.commit()
    return {"ok": True}
