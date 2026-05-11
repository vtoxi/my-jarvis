from fastapi import APIRouter, Depends, Query

from app.agents.registry import STATIC_AGENTS
from app.core.deps import get_memory
from app.memory.store import MemoryStore
from app.schemas.agents import AgentStatusItem, AgentsStatusResponse

router = APIRouter(tags=["agents"])


@router.get("/agents/status", response_model=AgentsStatusResponse)
async def agents_status(
    session_id: str | None = Query(default=None, max_length=128),
    memory: MemoryStore = Depends(get_memory),
) -> AgentsStatusResponse:
    items: list[AgentStatusItem] = []
    for row in STATIC_AGENTS:
        last = await memory.last_event_for_agent(row["id"], session_id)
        items.append(
            AgentStatusItem(
                id=row["id"],
                name=row["name"],
                phase=int(row["phase"]),
                enabled=bool(row["enabled"]),
                description=str(row["description"]),
                last_event=last,
            ),
        )
    return AgentsStatusResponse(agents=items)
