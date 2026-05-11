from pydantic import BaseModel, Field


class AgentStatusItem(BaseModel):
    id: str
    name: str
    phase: int
    enabled: bool
    description: str
    last_event: dict[str, object] | None = None


class AgentsStatusResponse(BaseModel):
    agents: list[AgentStatusItem]
