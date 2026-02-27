import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.auth import get_current_user
from app.core.database import get_db, AsyncSessionLocal
from app.models.org import OnboardingConfig
from app.models.task import Task, TaskEvent
from app.models.user import User
from app.schemas.task import TaskCreate, TaskCreated, TaskOut, TaskEventOut

router = APIRouter()


async def _get_user_org(user_data: dict, db: AsyncSession) -> tuple[User, int]:
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    if not user or not user.org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Onboarding not complete")
    return user, user.org_id


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

    # Queue via Celery
    from app.pipeline.task_queue import run_pipeline
    run_pipeline.delay(str(task.id))

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
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at)
    )
    events = result.scalars().all()

    task_out = TaskOut.model_validate(task)
    task_out.events = [TaskEventOut.model_validate(e) for e in events]
    return task_out


@router.get("/task/{task_id}/stream")
async def stream_task(
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
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        last_event_id = 0
        terminal_statuses = {"done", "failed", "paused"}
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
                        "agent": event.agent_name,
                        "type": event.event_type,
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
