from pydantic import BaseModel


class SkillOut(BaseModel):
    id: int
    key: str
    name: str
    description: str | None = None
    category: str
    stack_chips: list[str] = []
    is_preset: bool = False


class SkillDetailOut(SkillOut):
    system_prompt: str = ""
    allowed_extensions: list[str] = []
    allowed_dirs: list[str] = []
    context_priorities: list[str] = []


class SkillAssignPayload(BaseModel):
    skill_ids: list[int] = []
    preset: str | None = None  # e.g., "fullstack" — auto-resolves to skill IDs


class SkillCreatePayload(BaseModel):
    key: str
    name: str
    description: str = ""
    category: str
    stack_chips: list[str] = []
    system_prompt: str = ""
    allowed_extensions: list[str] = []
    allowed_dirs: list[str] = []
    context_priorities: list[str] = []


class SkillUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    allowed_extensions: list[str] | None = None
    allowed_dirs: list[str] | None = None
    context_priorities: list[str] | None = None
