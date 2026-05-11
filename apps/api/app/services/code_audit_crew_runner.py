from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from crewai import Agent, Crew, LLM, Process, Task

from app.agents import code_audit_agent as ca_defs
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CodeAuditResult:
    synthesis_markdown: str
    debt_score: int
    categories: dict[str, list[str]]


def _debt_from_tools(tools: dict[str, object]) -> int:
    penalties = 0
    for _k, v in tools.items():
        if not isinstance(v, dict):
            continue
        if v.get("skipped"):
            continue
        if v.get("ok") is False:
            penalties += 12
        elif v.get("exit_code", 0) not in (0, None):
            penalties += 12
    return max(0, min(100, 100 - penalties))


def _stub(tools_summary: dict[str, object], mode: str) -> CodeAuditResult:
    blob = json.dumps(tools_summary, indent=2)[:4000]
    return CodeAuditResult(
        synthesis_markdown=(
            f"## Code audit ({mode}) — stub\n\n"
            "_`JARVIS_LLM_STUB` — enable Ollama for narrative synthesis._\n\n"
            f"```json\n{blob}\n```\n"
        ),
        debt_score=_debt_from_tools(tools_summary),
        categories={"stability": [], "performance": [], "architecture": [], "ux": [], "security": []},
    )


def run_code_audit_crew(
    *,
    settings: Settings,
    tools_summary: dict[str, object],
    mode: str,
    model: str,
) -> CodeAuditResult:
    tools_json = json.dumps(tools_summary, indent=2)[:14000]
    base_debt = _debt_from_tools(tools_summary)
    if settings.llm_stub:
        r = _stub(tools_summary, mode)
        return CodeAuditResult(r.synthesis_markdown, base_debt, r.categories)

    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.2,
    )
    agent = Agent(
        role=ca_defs.CODE_AUDIT_ROLE,
        goal=ca_defs.CODE_AUDIT_GOAL,
        backstory=ca_defs.CODE_AUDIT_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=5,
    )
    improve_hint = (
        "Emphasize refactors, modularity, and UX consistency."
        if mode == "improve"
        else "Emphasize correctness and test failures first."
    )
    task = Task(
        description=(
            f"Mode: **{mode}**. {improve_hint}\n\n"
            "### Tool output (JSON)\n"
            f"```json\n{tools_json}\n```\n\n"
            "Respond in markdown with:\n"
            "## Executive summary\n"
            "## Top risks\n"
            "## Quick wins\n"
            "## Category A — Stability\n(bullets)\n"
            "## Category B — Performance\n"
            "## Category C — Architecture\n"
            "## Category D — UX\n"
            "## Category E — Security\n"
        ),
        expected_output="Markdown with the requested headings.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=settings.crew_verbose)
    logger.info("code audit crew kickoff mode=%s model=ollama/%s", mode, tag)
    crew.kickoff()
    raw = str(getattr(task, "output", None) or "").strip() or str(crew)

    def _cat(letter: str, title: str) -> list[str]:
        m = re.search(rf"## Category {letter} — {title}\s*\n(.*?)(?=\n## |\Z)", raw, re.S | re.I)
        if not m:
            return []
        lines = [ln.strip().lstrip("-*").strip() for ln in m.group(1).splitlines() if ln.strip()]
        return [ln for ln in lines if ln][:24]

    cats = {
        "stability": _cat("A", "Stability"),
        "performance": _cat("B", "Performance"),
        "architecture": _cat("C", "Architecture"),
        "ux": _cat("D", "UX"),
        "security": _cat("E", "Security"),
    }
    return CodeAuditResult(synthesis_markdown=raw[:24000], debt_score=base_debt, categories=cats)
