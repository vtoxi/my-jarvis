from typing import Literal

from pydantic import BaseModel, Field


class MemoryMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class MemoryGetResponse(BaseModel):
    session_id: str
    messages: list[MemoryMessage]
    preferences: dict[str, object] = Field(default_factory=dict)


class MemoryAppendRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=8000)
