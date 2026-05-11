from fastapi import APIRouter, Depends, Query

from app.core.deps import get_memory
from app.memory.store import MemoryStore
from app.schemas.memory import MemoryAppendRequest, MemoryGetResponse, MemoryMessage

router = APIRouter(tags=["memory"])


@router.get("/memory", response_model=MemoryGetResponse)
async def get_memory(
    session_id: str = Query(min_length=8, max_length=128),
    memory: MemoryStore = Depends(get_memory),
) -> MemoryGetResponse:
    rows = await memory.list_messages(session_id, limit=80)
    prefs = await memory.kv_get(f"session_prefs:{session_id}")
    payload: dict[str, object] = prefs if isinstance(prefs, dict) else {}
    return MemoryGetResponse(
        session_id=session_id,
        messages=[MemoryMessage(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in rows],
        preferences=payload,
    )


@router.post("/memory", response_model=MemoryMessage)
async def append_memory(req: MemoryAppendRequest, memory: MemoryStore = Depends(get_memory)) -> MemoryMessage:
    msg = await memory.append_message(req.session_id, req.role, req.content)
    return MemoryMessage(id=msg.id, role=msg.role, content=msg.content, created_at=msg.created_at)
