from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str = Field(min_length=8, max_length=128)
    model: str | None = Field(default=None, description="Ollama model tag without ollama/ prefix")


class AgentUsed(BaseModel):
    id: str
    name: str
    summary: str


class CommandResponse(BaseModel):
    reply: str
    session_id: str
    model: str
    agents_used: list[AgentUsed] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
