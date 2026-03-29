import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db, AsyncSessionLocal
from app.core.config import settings
from app.models.task import Task, TaskEvent
from app.models.user import User
from app.schemas.task import TaskCreate, TaskCreated, TaskOut, TaskEventOut

router = APIRouter()

# Bearer scheme that returns None instead of raising when header is absent
_optional_bearer = HTTPBearer(auto_error=False)


async def _get_user_org(user_data: dict, db: AsyncSession) -> tuple[User, int]:
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    if not user or not user.org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Onboarding not complete")
    return user, user.org_id


async def _verify_token_raw(token: str) -> dict:
    """Verify a raw JWT and return user dict."""
    from clerk_backend_api.security import verify_token_async, VerifyTokenOptions
    try:
        payload = await verify_token_async(
            token,
            VerifyTokenOptions(secret_key=settings.clerk_secret_key),
        )
        return {"user_id": payload["sub"], "session_id": payload.get("sid", "")}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def _get_sse_user(
    token_query: Optional[str] = Query(None, alias="token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> dict:
    """Auth for SSE — accepts Bearer header OR ?token= query param (EventSource limitation)."""
    if settings.bypass_auth:
        return {"user_id": settings.bypass_auth_user_id, "session_id": "dev"}
    raw = credentials.credentials if credentials else token_query
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    return await _verify_token_raw(raw)


@router.post("/task", response_model=TaskCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    payload: TaskCreate,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, org_id = await _get_user_org(user_data, db)

    task = Task(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user.id,
        description=payload.description,
        jira_ticket_id=payload.jira_ticket_id,
        status="queued",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Queue via Celery — use legacy pipeline (proven working)
    from app.pipeline.task_queue import run_pipeline
    celery_result = run_pipeline.delay(str(task.id))
    task.celery_task_id = celery_result.id
    await db.commit()

    return TaskCreated(task_id=task.id, status="queued")


@router.get("/task/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: uuid.UUID,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = await _get_user_org(user_data, db)

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.org_id == org_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    result = await db.execute(
        select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at)
    )
    events = result.scalars().all()

    task_out = TaskOut.model_validate(task)
    task_out.events = [TaskEventOut.model_validate(e) for e in events]
    return task_out


@router.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: uuid.UUID,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = await _get_user_org(user_data, db)

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.org_id == org_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status not in ("queued", "running", "waiting_clarification", "in_review"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot cancel a task with status '{task.status}'")

    # Revoke the Celery task — terminate=True sends SIGTERM to the worker process
    if task.celery_task_id:
        from app.celery_app import celery_app
        celery_app.control.revoke(task.celery_task_id, terminate=True, signal="SIGTERM")

    task.status = "cancelled"
    from datetime import datetime, timezone
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}



@router.post("/poll/pr-outcomes")
async def trigger_poll_pr_outcomes(
    user_data: dict = Depends(get_current_user),
):
    """Manually trigger PR outcome polling."""
    from app.pipeline.task_queue import poll_pr_outcomes
    poll_pr_outcomes.delay()
    return {"ok": True, "message": "PR outcome poll queued"}


@router.post("/poll/clarifications")
async def trigger_poll_clarifications(
    user_data: dict = Depends(get_current_user),
):
    """Manually trigger clarification polling."""
    from app.pipeline.task_queue import poll_clarifications
    poll_clarifications.delay()
    return {"ok": True, "message": "Clarification poll queued"}


@router.post("/poll/convention-refresh")
async def trigger_convention_refresh(
    user_data: dict = Depends(get_current_user),
):
    """Manually trigger convention refresh for all orgs."""
    from app.pipeline.task_queue import refresh_conventions_all_orgs
    refresh_conventions_all_orgs.delay()
    return {"ok": True, "message": "Convention refresh queued"}


@router.get("/task/{task_id}/stream")
async def stream_task(
    task_id: uuid.UUID,
    user_data: dict = Depends(_get_sse_user),
    db: AsyncSession = Depends(get_db),
):
    _, org_id = await _get_user_org(user_data, db)

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.org_id == org_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    async def event_generator():
        last_event_id = 0
        terminal_statuses = {"done", "failed", "paused", "cancelled", "waiting_clarification", "in_review"}
        max_polls = 300  # 5 minutes at 1s intervals

        for _ in range(max_polls):
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(TaskEvent)
                    .where(TaskEvent.task_id == task_id, TaskEvent.id > last_event_id)
                    .order_by(TaskEvent.created_at)
                )
                new_events = result.scalars().all()

                for event in new_events:
                    data = {
                        "id": event.id,
                        "agent_name": event.agent_name,
                        "event_type": event.event_type,
                        "message": event.message,
                        "payload": event.payload,
                        "ts": event.created_at.isoformat(),
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_event_id = event.id

                result = await session.execute(select(Task.status).where(Task.id == task_id))
                current_status = result.scalar_one()

            if current_status in terminal_statuses:
                yield f"data: {json.dumps({'type': 'terminal', 'status': current_status})}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
