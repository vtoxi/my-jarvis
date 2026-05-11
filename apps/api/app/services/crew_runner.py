from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.agents.jarvis_crew import run_jarvis_crew
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class AgentRunSummary:
    id: str
    name: str
    summary: str


@dataclass
class CommandResult:
    reply: str
    model: str
    agents_used: list[AgentRunSummary]
    errors: list[str]


def run_command_brain(
    *,
    settings: Settings,
    user_message: str,
    history_block: str,
    model: str,
    force_stub: bool | None = None,
) -> CommandResult:
    errors: list[str] = []
    stub = settings.llm_stub if force_stub is None else force_stub

    if stub:
        reply = (
            "**[LLM stub mode]**\n\n"
            "Acknowledged. In production this route runs the local Crew (Planner → Commander) against Ollama.\n\n"
            f"_Your message:_ {user_message.strip()[:400]}"
        )
        return CommandResult(
            reply=reply,
            model=model,
            agents_used=[
                AgentRunSummary(id="planner", name="Planner", summary="Stub: planning bypassed"),
                AgentRunSummary(id="commander", name="Commander", summary="Stub: synthesized placeholder"),
            ],
            errors=errors,
        )

    try:
        result = run_jarvis_crew(
            settings=settings,
            user_message=user_message,
            history_block=history_block,
            model=model,
        )
        agents_used = [
            AgentRunSummary(id="planner", name="Planner", summary=result.planner_excerpt or "Planner output captured"),
            AgentRunSummary(
                id="commander",
                name="Commander",
                summary=(result.reply[:320] + "…") if len(result.reply) > 320 else result.reply,
            ),
        ]
        return CommandResult(reply=result.reply, model=model, agents_used=agents_used, errors=errors)
    except Exception as exc:  # noqa: BLE001 — surface to client with log
        logger.exception("crew run failed")
        errors.append(str(exc))
        return CommandResult(
            reply=(
                "JARVIS encountered an error while engaging the local crew. "
                "Verify Ollama is running and the selected model is pulled."
            ),
            model=model,
            agents_used=[],
            errors=errors,
        )


def summaries_to_json(rows: list[AgentRunSummary]) -> list[dict[str, Any]]:
    return [{"id": r.id, "name": r.name, "summary": r.summary} for r in rows]
