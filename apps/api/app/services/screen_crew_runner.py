from __future__ import annotations

import logging
from dataclasses import dataclass

from crewai import Agent, Crew, LLM, Process, Task

from app.agents import context_agent as ctx_defs
from app.agents import productivity_copilot_agent as cop_defs
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ScreenCrewResult:
    context_markdown: str
    copilot_markdown: str


def _stub(evidence: str) -> ScreenCrewResult:
    clip = (evidence or "").strip()
    if len(clip) > 900:
        clip = clip[:899] + "…"
    return ScreenCrewResult(
        context_markdown=(
            "## Situational read (stub)\n\n"
            "_`JARVIS_LLM_STUB` is on — enable Ollama for live copilot._\n\n"
            f"```\n{clip}\n```\n"
        ),
        copilot_markdown=(
            "## Suggested moves\n- Disable stub and re-run suggestions.\n\n"
            "## Watchouts\n- Intelligence offline.\n"
        ),
    )


def run_screen_intel_crew(*, settings: Settings, evidence_block: str, assist_mode: str, model: str) -> ScreenCrewResult:
    if settings.llm_stub:
        return _stub(evidence_block)

    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.2,
    )

    analyst = Agent(
        role=ctx_defs.CONTEXT_AGENT_ROLE,
        goal=ctx_defs.CONTEXT_AGENT_GOAL,
        backstory=ctx_defs.CONTEXT_AGENT_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=4,
    )
    copilot = Agent(
        role=cop_defs.COPILOT_ROLE,
        goal=cop_defs.COPILOT_GOAL,
        backstory=cop_defs.COPILOT_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=5,
    )

    ctx_task = Task(
        description=(
            f"Assist mode (operator preference): **{assist_mode}**.\n\n"
            "### Evidence (foreground + on-screen text excerpt)\n"
            f"{evidence_block}\n\n"
            "Output markdown with:\n"
            "## Current context\n"
            "## Likely objective\n"
            "## Mode signals (bullets)\n"
            "Do not fabricate text not supported by evidence."
        ),
        expected_output="Markdown situational brief.",
        agent=analyst,
    )

    cop_task = Task(
        description=(
            "Use the Context Analyst output in your context. Same assist mode and evidence rules apply. "
            "Respect privacy: no guilt, no surveillance tone."
        ),
        expected_output="Markdown with ## Suggested moves and ## Watchouts.",
        agent=copilot,
        context=[ctx_task],
    )

    crew = Crew(
        agents=[analyst, copilot],
        tasks=[ctx_task, cop_task],
        process=Process.sequential,
        verbose=settings.crew_verbose,
    )
    logger.info("screen intel crew kickoff model=ollama/%s", tag)
    crew.kickoff()

    def _task_text(task: object) -> str:
        try:
            out = getattr(task, "output", None)
            if out is None:
                return ""
            return str(getattr(out, "raw", out))
        except Exception:
            return ""

    ctx_out = _task_text(ctx_task).strip() or "_No context output._"
    cop_out = _task_text(cop_task).strip() or "_No copilot output._"
    return ScreenCrewResult(context_markdown=ctx_out, copilot_markdown=cop_out)
