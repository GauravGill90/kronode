"""
Celery task integration for the multi-flow orchestrator.

Uses LangGraph-based MultiFlowOrchestrator with flow classification.
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.models.task import Task, TaskStatus
from app.core.database import get_db_session
from sqlalchemy import select

from .multi_flow_orchestrator import run_pipeline, resume_pipeline
from .state import PipelineState, PipelineStatus

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE HELPERS
# ============================================================================


async def load_task_from_db(task_id: str) -> Optional[Task]:
    """Load task from database."""
    async with get_db_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()


async def load_state_from_db(task_id: str) -> Optional[PipelineState]:
    """
    Load pipeline state from database.

    Assumes Task model has a 'pipeline_state' JSONB column.
    """
    task = await load_task_from_db(task_id)

    if not task:
        return None

    # Check if task has saved state
    if hasattr(task, 'pipeline_state') and task.pipeline_state:
        return PipelineState.from_dict(task.pipeline_state)

    # Otherwise create fresh state
    return PipelineState(
        task_id=str(task.id),
        org_id=str(task.org_id),
        task_description=task.description,
        user_id=str(task.user_id) if task.user_id else None,
    )


async def save_state_to_db(task_id: str, state: PipelineState):
    """Save pipeline state to database."""
    async with get_db_session() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return

        # Save state to JSONB column (if exists)
        if hasattr(task, 'pipeline_state'):
            task.pipeline_state = state.to_dict()

        # Update task fields
        status_mapping = {
            PipelineStatus.DONE: TaskStatus.DONE,
            PipelineStatus.FAILED: TaskStatus.FAILED,
            PipelineStatus.CANCELLED: TaskStatus.CANCELLED,
            PipelineStatus.WAITING_CLARIFICATION: TaskStatus.WAITING_CLARIFICATION,
            PipelineStatus.IN_REVIEW: TaskStatus.IN_REVIEW,
            PipelineStatus.RUNNING: TaskStatus.RUNNING,
            PipelineStatus.PAUSED: TaskStatus.PAUSED,
        }

        task.status = status_mapping.get(state.status, TaskStatus.RUNNING)

        if state.pr_url:
            task.pr_url = state.pr_url
        if state.pr_number:
            task.pr_number = state.pr_number
        if state.branch_name:
            task.branch_name = state.branch_name
        if state.errors:
            task.error_message = "\n".join(state.errors)

        if state.status in [PipelineStatus.DONE, PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
            task.completed_at = datetime.utcnow()

        await db.commit()


# ============================================================================
# CELERY TASKS
# ============================================================================


@celery_app.task(name="orchestration.run_pipeline", bind=True)
def run_pipeline_task(self, task_id: str, action: Optional[str] = None):
    """
    Celery task to run the pipeline with flow classification.

    The MultiFlowOrchestrator will classify the input to determine which
    flow to execute (ticket_implementation, onboarding, continuous_ingestion).

    Args:
        task_id: Task ID to process
        action: Optional explicit action (implement, onboard, ingest, etc.)

    Returns:
        Dict with execution results
    """
    logger.info(f"[Celery] Starting pipeline for task {task_id} (action={action})")

    try:
        # Load task from DB to get org_id and description
        async def load_and_run():
            task = await load_task_from_db(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Run pipeline with flow classification
            final_state = await run_pipeline(
                org_id=str(task.org_id),
                task_id=task_id,
                task_description=task.description,
                user_id=str(task.user_id) if task.user_id else None,
                action=action or 'implement'  # Default to ticket implementation
            )

            # Save state to DB
            await save_state_to_db(task_id, final_state)

            return final_state

        final_state = asyncio.run(load_and_run())

        logger.info(
            f"[Celery] Pipeline completed for task {task_id}: "
            f"flow={final_state.flow_name}, status={final_state.status}"
        )

        return {
            "success": True,
            "task_id": task_id,
            "flow_name": final_state.flow_name,
            "status": final_state.status.value,
            "pr_url": final_state.pr_url,
        }

    except Exception as e:
        logger.error(f"[Celery] Pipeline failed for task {task_id}: {e}", exc_info=True)

        # Retry logic
        if self.request.retries < 2:
            logger.info(f"[Celery] Retrying task {task_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e, countdown=60)

        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
        }


@celery_app.task(name="orchestration.resume_pipeline", bind=True)
def resume_pipeline_task(
    self,
    task_id: str,
    clarification_answer: Optional[str] = None,
    pr_feedback: Optional[str] = None
):
    """
    Celery task to resume a paused pipeline.

    Args:
        task_id: Task ID to resume
        clarification_answer: Answer to clarification
        pr_feedback: PR feedback

    Returns:
        Dict with execution results
    """
    logger.info(f"[Celery] Resuming pipeline for task {task_id}")

    try:
        # Load state from DB
        state = asyncio.run(load_state_from_db(task_id))

        if not state:
            raise ValueError(f"Task {task_id} not found or no state saved")

        # Resume pipeline
        final_state = asyncio.run(
            resume_pipeline(
                state,
                clarification_answer=clarification_answer,
                pr_feedback=pr_feedback
            )
        )

        # Save state
        asyncio.run(save_state_to_db(task_id, final_state))

        logger.info(f"[Celery] Pipeline resumed for task {task_id}: {final_state.status}")

        return {
            "success": True,
            "task_id": task_id,
            "status": final_state.status.value,
            "pr_url": final_state.pr_url,
        }

    except Exception as e:
        logger.error(f"[Celery] Resume failed for task {task_id}: {e}", exc_info=True)

        if self.request.retries < 2:
            raise self.retry(exc=e, countdown=60)

        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
        }


@celery_app.task(name="orchestration.cancel_pipeline")
def cancel_pipeline_task(task_id: str):
    """
    Celery task to cancel a pipeline.

    Args:
        task_id: Task ID to cancel

    Returns:
        Dict with result
    """
    logger.info(f"[Celery] Cancelling pipeline for task {task_id}")

    try:
        async def cancel():
            async with get_db_session() as db:
                result = await db.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()

                if not task:
                    return False

                task.status = TaskStatus.CANCELLED
                await db.commit()
                return True

        success = asyncio.run(cancel())

        return {
            "success": success,
            "task_id": task_id,
        }

    except Exception as e:
        logger.error(f"[Celery] Cancel failed for task {task_id}: {e}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
        }


# ============================================================================
# PERIODIC TASKS (Celery Beat)
# ============================================================================


@celery_app.task(name="orchestration.poll_clarifications")
def poll_clarifications_task():
    """
    Poll for clarification responses and resume pipelines.

    Runs every 30 seconds via Celery Beat.
    """
    logger.debug("[Celery Beat] Polling for clarification responses")

    try:
        async def poll():
            from app.services.slack_service import check_thread_for_reply

            async with get_db_session() as db:
                # Find tasks waiting for clarification
                result = await db.execute(
                    select(Task).where(
                        Task.status == TaskStatus.WAITING_CLARIFICATION
                    )
                )
                waiting_tasks = result.scalars().all()

                for task in waiting_tasks:
                    # Check for Slack reply
                    slack_thread_ts = None
                    if hasattr(task, 'pipeline_state') and task.pipeline_state:
                        slack_thread_ts = task.pipeline_state.get('slack_thread_ts')

                    if slack_thread_ts:
                        try:
                            reply = await check_thread_for_reply(slack_thread_ts)

                            if reply:
                                logger.info(f"[Celery Beat] Clarification received for task {task.id}")
                                # Trigger resume
                                resume_pipeline_task.delay(
                                    str(task.id),
                                    clarification_answer=reply
                                )
                                continue
                        except Exception as e:
                            logger.error(f"[Celery Beat] Error checking Slack for task {task.id}: {e}")

                    # Check for timeout (24 hours)
                    waiting_duration = datetime.utcnow() - task.updated_at
                    if waiting_duration > timedelta(hours=24):
                        logger.warning(f"[Celery Beat] Task {task.id} timed out waiting for clarification")
                        task.status = TaskStatus.FAILED
                        task.error_message = "Timed out waiting for clarification (24h)"
                        await db.commit()

        asyncio.run(poll())

    except Exception as e:
        logger.error(f"[Celery Beat] Error polling clarifications: {e}", exc_info=True)


@celery_app.task(name="orchestration.poll_pr_outcomes")
def poll_pr_outcomes_task():
    """
    Poll PR merge status and handle outcomes.

    Runs every 60 seconds via Celery Beat.
    """
    logger.debug("[Celery Beat] Polling PR outcomes")

    try:
        async def poll():
            from app.services.github_service import get_pr_status, get_pr_reviews

            async with get_db_session() as db:
                # Find tasks in review with PR
                result = await db.execute(
                    select(Task).where(
                        Task.status == TaskStatus.IN_REVIEW,
                        Task.pr_number.isnot(None)
                    )
                )
                review_tasks = result.scalars().all()

                for task in review_tasks:
                    try:
                        pr_status = await get_pr_status(task.org_id, task.pr_number)

                        if pr_status == "merged":
                            logger.info(f"[Celery Beat] PR merged for task {task.id}")
                            task.status = TaskStatus.DONE
                            task.completed_at = datetime.utcnow()
                            await db.commit()

                        elif pr_status == "changes_requested":
                            logger.info(f"[Celery Beat] Changes requested for task {task.id}")
                            # Get review comments
                            reviews = await get_pr_reviews(task.org_id, task.pr_number)
                            feedback = _format_pr_feedback(reviews)

                            # Trigger revision
                            resume_pipeline_task.delay(
                                str(task.id),
                                pr_feedback=feedback
                            )

                        elif pr_status == "closed":
                            logger.warning(f"[Celery Beat] PR closed without merge for task {task.id}")
                            task.status = TaskStatus.FAILED
                            task.error_message = "PR closed without merge"
                            await db.commit()

                    except Exception as e:
                        logger.error(f"[Celery Beat] Error checking PR for task {task.id}: {e}")

        asyncio.run(poll())

    except Exception as e:
        logger.error(f"[Celery Beat] Error polling PR outcomes: {e}", exc_info=True)


def _format_pr_feedback(reviews: list) -> str:
    """Format PR reviews into feedback string."""
    feedback_parts = []

    for review in reviews:
        if review.get("state") == "CHANGES_REQUESTED":
            feedback_parts.append(f"Review by {review['user']['login']}:")
            feedback_parts.append(review.get("body", "(no comment)"))
            feedback_parts.append("")

    return "\n".join(feedback_parts) if feedback_parts else "Changes requested (no details)"


@celery_app.task(name="orchestration.run_continuous_ingestion")
def run_continuous_ingestion_task(org_id: str):
    """
    Run continuous ingestion for an organization.

    This task should be scheduled to run periodically (e.g., hourly or daily)
    to keep team context up-to-date.

    Args:
        org_id: Organization ID to ingest data for

    Returns:
        Dict with execution results
    """
    logger.info(f"[Celery] Running continuous ingestion for org {org_id}")

    try:
        async def run_ingestion():
            # Generate unique task ID for this ingestion run
            import uuid
            task_id = f"ingestion_{org_id}_{uuid.uuid4().hex[:8]}"

            # Run ingestion flow
            final_state = await run_pipeline(
                org_id=org_id,
                task_id=task_id,
                action='ingest',
                task_description=f"Continuous ingestion for org {org_id}",
                scheduled=True,
                background_task=True
            )

            return final_state

        final_state = asyncio.run(run_ingestion())

        logger.info(
            f"[Celery] Continuous ingestion completed for org {org_id}: {final_state.status}"
        )

        return {
            "success": True,
            "org_id": org_id,
            "status": final_state.status.value,
        }

    except Exception as e:
        logger.error(f"[Celery] Ingestion failed for org {org_id}: {e}", exc_info=True)
        return {
            "success": False,
            "org_id": org_id,
            "error": str(e),
        }


# ============================================================================
# BEAT SCHEDULE CONFIGURATION
# ============================================================================

# Add this to celery_app.py:
"""
celery_app.conf.beat_schedule = {
    "poll_clarifications": {
        "task": "orchestration.poll_clarifications",
        "schedule": 30.0,  # Every 30 seconds
    },
    "poll_pr_outcomes": {
        "task": "orchestration.poll_pr_outcomes",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Example: Run continuous ingestion daily at 2 AM for all orgs
    # "continuous_ingestion_org_123": {
    #     "task": "orchestration.run_continuous_ingestion",
    #     "schedule": crontab(hour=2, minute=0),
    #     "args": ("org_123",),
    # },
}
"""
