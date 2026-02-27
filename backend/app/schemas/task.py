import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskCreate(BaseModel):
    description: str
    jira_ticket_id: str | None = None


class TaskEventOut(BaseModel):
    id: int
    agent_name: str
    event_type: str
    message: str
    payload: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: uuid.UUID
    description: str
    status: str
    jira_ticket_id: str | None = None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    events: list[TaskEventOut] = []

    model_config = {"from_attributes": True}


class TaskCreated(BaseModel):
    task_id: uuid.UUID
    status: str
