from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from crewai import Agent, Crew, LLM, Process, Task

from app.agents import idle_learning_agent as idle_defs
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class IdleLearningResult:
    report_markdown: str
    actions_proposed: list[str]


def _stub(health_json: str, log_tail: str, knowledge_digest: str) -> IdleLearningResult:
    kg = ""
    if knowledge_digest.strip():
        kg = f"\n### Local knowledge (retrieved)\n{knowledge_digest.strip()[:4000]}\n"
    body = (
        "## Idle learning report (stub)\n\n"
        "_`JARVIS_LLM_STUB` — enable Ollama for narrative synthesis._\n\n"
        "### Signals reviewed\n- Local health JSON digest\n- API log tail (truncated)\n"
        f"{kg}\n"
        "### Safe suggestions\n"
        "1. Re-run with stub off after Ollama is up.\n"
        "2. Use `/evolution/twin` PATCH to record preferences explicitly.\n\n"
        "### Explicit non-actions\n"
        "- No network crawl\n- No silent config writes\n"
    )
    return IdleLearningResult(report_markdown=body, actions_proposed=["Enable Ollama; disable LLM stub for idle synthesis"])


def run_idle_learning_crew(
    *,
    settings: Settings,
    health_json: str,
    log_tail: str,
    twin_json: str,
    model: str,
    knowledge_digest: str = "",
) -> IdleLearningResult:
    if settings.llm_stub:
        return _stub(health_json, log_tail, knowledge_digest)

    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.12,
    )
    agent = Agent(
        role=idle_defs.IDLE_ROLE,
        goal=idle_defs.IDLE_GOAL,
        backstory=idle_defs.IDLE_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=4,
    )
    task = Task(
        description=(
            "### Twin snapshot (JSON)\n"
            f"```json\n{twin_json[:6000]}\n```\n\n"
            "### Health (JSON)\n"
            f"```json\n{health_json[:8000]}\n```\n\n"
            "### Log tail\n"
            f"```\n{log_tail[:5000]}\n```\n\n"
            + (
                f"### Retrieved local knowledge (cosine-ranked; not external crawl)\n{knowledge_digest.strip()[:6000]}\n\n"
                if knowledge_digest.strip()
                else ""
            )
            + "Produce markdown with:\n"
            "## Idle observations\n"
            "## Workflow hypotheses (bullets; mark confidence low/med/high)\n"
            "## Recommended next steps (numbered; each must be safe and local)\n"
            "## Requires human approval\n"
            "(list any step that would change code, secrets, or external systems)\n"
        ),
        expected_output="Markdown report for operator review.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=settings.crew_verbose)
    logger.info("idle learning crew kickoff model=ollama/%s", tag)
    crew.kickoff()
    raw = str(getattr(task, "output", None) or "").strip() or str(crew)
    actions: list[str] = []
    m = re.search(r"## Recommended next steps(.*?)## Requires human approval", raw, re.S | re.I)
    if m:
        for line in m.group(1).splitlines():
            line = re.sub(r"^\d+\.\s*", "", line.strip())
            if line.startswith("- "):
                line = line[2:].strip()
            if line and not line.startswith("#"):
                actions.append(line[:500])
    return IdleLearningResult(report_markdown=raw[:100_000], actions_proposed=actions[:30])
