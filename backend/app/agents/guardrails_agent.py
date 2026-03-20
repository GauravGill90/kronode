import logging
import os

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)


def _is_restricted(path: str, restricted_paths: list[str]) -> bool:
    for rp in restricted_paths:
        rp_norm = rp.rstrip("/")
        if path == rp_norm or path.startswith(rp_norm + "/") or path.startswith(rp):
            return True
    return False


def _is_root_level(path: str) -> bool:
    """Root-level files (Makefile, README.md, docker-compose.yml, etc.) are always in scope."""
    return "/" not in path


def _allowed_dir(path: str, allowed_dirs: list[str]) -> bool:
    if _is_root_level(path):
        return True
    return not allowed_dirs or any(path.startswith(d) for d in allowed_dirs)


class GuardrailsAgent(AgentBase):
    display_name = "Guardrails"

    async def run(self, context: dict) -> dict:
        guardrails = context.get("guardrails", {}) or {}
        restricted_paths = guardrails.get("restricted_paths", [])
        max_files = guardrails.get("max_files_per_task", 20)
        risk_level = guardrails.get("risk_level", "balanced")

        # Read composed skill scope from context (set by pipeline.py)
        allowed_dirs = context.get("allowed_dirs", [])
        allowed_extensions = set(context.get("allowed_extensions", []))

        # Flatten files_affected from all planner subtasks (deduplicated)
        planner_result = context.get("planner_agent", {})
        subtasks = planner_result.get("subtasks", [])
        estimated_files = planner_result.get("estimated_files", 0)

        all_files: list[str] = []
        seen: set[str] = set()
        for subtask in subtasks:
            for path in subtask.get("files_affected", []):
                if path not in seen:
                    all_files.append(path)
                    seen.add(path)

        violations: list[str] = []

        # Check 1: restricted paths (org config)
        for path in all_files:
            if _is_restricted(path, restricted_paths):
                violations.append(f"Restricted path: {path}")

        # Check 2: profile allowed dirs (scope enforcement)
        for path in all_files:
            if not _allowed_dir(path, allowed_dirs):
                violations.append(
                    f"Outside {profile.PROFILE_NAME} scope: {path} "
                    f"(allowed dirs: {', '.join(allowed_dirs[:3])}{'...' if len(allowed_dirs) > 3 else ''})"
                )

        # Check 3: profile allowed extensions (root-level files are exempt)
        for path in all_files:
            if _is_root_level(path):
                continue
            ext = os.path.splitext(path)[1]
            if ext and ext not in allowed_extensions:
                violations.append(f"Disallowed extension {ext} for {profile.PROFILE_NAME}: {path}")

        # Check 4: max files per task
        if estimated_files > max_files:
            violations.append(
                f"Estimated {estimated_files} files exceeds org limit of {max_files}"
            )

        # Check 5: conservative risk level hard cap
        if risk_level == "conservative" and estimated_files > 5:
            violations.append(
                f"Conservative risk level: {estimated_files} files planned (max 5 without manual approval)"
            )

        if violations:
            reason = f"Guardrails blocked {len(violations)} violation(s): " + "; ".join(violations[:3])
            if len(violations) > 3:
                reason += f" (and {len(violations) - 3} more)"
            logger.warning(f"[Guardrails] Blocked: {violations}")
            return {
                "blocked": True,
                "reason": reason,
                "violations": violations,
                "summary": reason,
            }

        n = estimated_files or len(all_files)
        if n <= 3:
            risk_cls, pr_size = "low", "small"
        elif n <= 10:
            risk_cls, pr_size = "medium", "medium"
        else:
            risk_cls, pr_size = "high", "large"

        summary = (
            f"Guardrails passed. {len(all_files)} file(s) checked. "
            f"Risk: {risk_cls}. PR size estimate: {pr_size}."
        )
        logger.info(f"[Guardrails] {summary}")
        return {
            "blocked": False,
            "violations": [],
            "summary": summary,
            "risk_classification": risk_cls,
            "pr_size_estimate": pr_size,
        }
