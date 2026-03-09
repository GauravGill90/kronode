from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, HttpUrl, field_validator


# ── Confluence ────────────────────────────────────────────────────────────────


class ConfluencePayload(BaseModel):
    """Payload for saving Confluence connector config."""

    base_url: str
    space_keys: List[str]
    include_labels: Optional[List[str]] = []

    @field_validator("base_url")
    @classmethod
    def base_url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("base_url is required")
        return v

    @field_validator("space_keys")
    @classmethod
    def at_least_one_space(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one space key is required")
        return [k.strip().upper() for k in v if k.strip()]


class ConfluenceTestPayload(BaseModel):
    """Payload for test-confluence endpoint."""

    base_url: str
    space_keys: List[str]
    include_labels: Optional[List[str]] = []

    @field_validator("base_url")
    @classmethod
    def base_url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("base_url is required")
        return v

    @field_validator("space_keys")
    @classmethod
    def at_least_one_space(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one space key is required")
        return [k.strip().upper() for k in v if k.strip()]


class ConfluenceSpaceResult(BaseModel):
    key: str
    name: str
    page_count: int


class ConfluenceTestResult(BaseModel):
    connected: bool
    spaces: List[ConfluenceSpaceResult]
