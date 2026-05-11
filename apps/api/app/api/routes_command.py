import anyio
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.deps import get_memory
from app.memory.store import MemoryStore
from app.schemas.command import AgentUsed, CommandRequest, CommandResponse
from app.services.crew_runner import summaries_to_json, run_command_brain

router = APIRouter(tags=["command"])


@router.post("/command", response_model=CommandResponse)
async def run_command(req: CommandRequest, memory: MemoryStore = Depends(get_memory)) -> CommandResponse:
    model = (req.model or settings.default_ollama_model).strip()
    await memory.append_message(req.session_id, "user", req.message)
    history = await memory.format_context(req.session_id, limit=20)

    def work():
        return run_command_brain(
            settings=settings,
            user_message=req.message,
            history_block=history,
            model=model,
        )

    result = await anyio.to_thread.run_sync(work)

    await memory.append_message(req.session_id, "assistant", result.reply)
    for agent in result.agents_used:
        await memory.log_agent_event(agent.id, req.session_id, agent.summary)

    return CommandResponse(
        reply=result.reply,
        session_id=req.session_id,
        model=model,
        agents_used=[AgentUsed(**row) for row in summaries_to_json(result.agents_used)],
        errors=result.errors,
    )
