from __future__ import annotations

import logging
from dataclasses import dataclass

from crewai import Agent, Crew, LLM, Process, Task

from app.agents import definitions as defs
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CrewRunResult:
    reply: str
    planner_excerpt: str


def _excerpt(text: str, max_len: int = 400) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def run_jarvis_crew(
    *,
    settings: Settings,
    user_message: str,
    history_block: str,
    model: str,
) -> CrewRunResult:
    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.2,
    )

    planner = Agent(
        role=defs.PLANNER_ROLE,
        goal=defs.PLANNER_GOAL,
        backstory=defs.PLANNER_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=4,
    )
    commander = Agent(
        role=defs.COMMANDER_ROLE,
        goal=defs.COMMANDER_GOAL,
        backstory=defs.COMMANDER_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=6,
    )

    plan_task = Task(
        description=(
            f"User message:\n{user_message}\n\n"
            f"Session context (recent turns):\n{history_block}\n\n"
            "Decide if structured planning is warranted. If yes, output a concise numbered markdown plan. "
            "If not, output NOT_APPLICABLE alone on the final line."
        ),
        expected_output="Either NOT_APPLICABLE or a numbered markdown plan.",
        agent=planner,
    )

    reply_task = Task(
        description=(
            f"User message:\n{user_message}\n\n"
            f"Session context:\n{history_block}\n\n"
            "Synthesize the final user-facing answer in markdown. "
            "If the Planner produced NOT_APPLICABLE, answer directly without inventing a plan. "
            "If a plan exists, integrate it crisply under a '## Mission plan' section."
        ),
        expected_output="Markdown suitable for a premium HUD assistant.",
        agent=commander,
        context=[plan_task],
    )

    crew = Crew(
        agents=[planner, commander],
        tasks=[plan_task, reply_task],
        process=Process.sequential,
        verbose=settings.crew_verbose,
    )

    logger.info("crew kickoff model=ollama/%s", tag)
    raw = crew.kickoff()

    planner_text = ""
    try:
        if getattr(plan_task, "output", None) is not None:
            out = plan_task.output
            planner_text = str(getattr(out, "raw", out))
    except Exception:
        planner_text = ""

    reply = str(raw).strip()
    if not reply:
        reply = "_No textual output returned from crew._"

    return CrewRunResult(reply=reply, planner_excerpt=_excerpt(planner_text))
