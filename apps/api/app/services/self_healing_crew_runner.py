from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from crewai import Agent, Crew, LLM, Process, Task

from app.agents import self_healing_agent as sh_defs
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SelfHealingResult:
    root_cause_hypothesis: str
    severity: str
    user_visible_summary: str
    recommended_commands: list[str]
    patch_plan: list[dict[str, object]]
    raw_markdown: str


def _stub(health_blob: str, log_tail: str, ctx: str | None) -> SelfHealingResult:
    summary = "Stub mode (`JARVIS_LLM_STUB`) — connect Ollama for live diagnosis."
    return SelfHealingResult(
        root_cause_hypothesis="Insufficient model signal; operator should review raw health JSON.",
        severity="info",
        user_visible_summary=summary,
        recommended_commands=[
            "Review GET /system/health JSON",
            "Check API logs under data_dir/logs",
            "Optional: POST /screen/capture — paste relevant OCR into the next POST /system/repair `context`",
        ],
        patch_plan=[],
        raw_markdown=f"### Context\n{ctx or '(none)'}\n\n### Health digest\n```json\n{health_blob[:2000]}\n```\n\n### Log tail\n```\n{log_tail[:1500]}\n```\n",
    )


def run_self_healing_crew(
    *,
    settings: Settings,
    health_json: str,
    log_tail: str,
    operator_context: str | None,
    model: str,
) -> SelfHealingResult:
    if settings.llm_stub:
        return _stub(health_json, log_tail, operator_context)

    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.15,
    )
    agent = Agent(
        role=sh_defs.SELF_HEALING_ROLE,
        goal=sh_defs.SELF_HEALING_GOAL,
        backstory=sh_defs.SELF_HEALING_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=4,
    )
    task = Task(
        description=(
            "### Operator notes\n"
            f"{operator_context or '(none)'}\n\n"
            "### Aggregated health (JSON)\n"
            f"```json\n{health_json[:12000]}\n```\n\n"
            "### Recent log lines\n"
            f"```\n{log_tail[:6000]}\n```\n\n"
            "If signals are insufficient, explicitly tell the operator to refresh screen context (JARVIS /screen/*) and "
            "paste OCR or error text — JARVIS must not claim it can move the mouse or keyboard without Hammerspoon "
            "operator approvals.\n\n"
            "Produce markdown with EXACTLY these headings in order:\n"
            "## Root cause hypothesis\n"
            "## Severity\n(one word: info|low|medium|high|critical)\n"
            "## User visible summary\n"
            "## Recommended commands\n"
            "(numbered shell commands the operator may run locally; no destructive rm/git reset unless clearly justified)\n"
            "## Patch plan\n"
            "(bullets: file path — rationale; empty if none)\n"
            "## Human approval\n"
            "(state that any code change requires explicit approval via JARVIS patch flow)\n"
        ),
        expected_output="Markdown with the requested headings.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=settings.crew_verbose)
    logger.info("self-healing crew kickoff model=ollama/%s", tag)
    crew.kickoff()
    raw = str(getattr(task, "output", None) or "").strip() or str(crew)

    def _sec(name: str) -> str:
        m = re.search(rf"## {re.escape(name)}\s*\n(.*?)(?=\n## |\Z)", raw, re.S | re.I)
        return (m.group(1).strip() if m else "")[:8000]

    sev = _sec("Severity").splitlines()[0].strip().lower() if _sec("Severity") else "info"
    if sev not in ("info", "low", "medium", "high", "critical"):
        sev = "info"
    cmds: list[str] = []
    cmd_block = _sec("Recommended commands")
    for line in cmd_block.splitlines():
        line = re.sub(r"^\d+\.\s*", "", line.strip())
        if line.startswith("`") and line.endswith("`"):
            line = line[1:-1]
        if line and not line.startswith("#"):
            cmds.append(line[:500])
    plans: list[dict[str, object]] = []
    for line in _sec("Patch plan").splitlines():
        t = line.strip().lstrip("-*").strip()
        if "—" in t or " - " in t:
            parts = re.split(r"\s[—-]\s", t, maxsplit=1)
            if len(parts) == 2:
                plans.append({"path": parts[0].strip(), "rationale": parts[1].strip()})
    return SelfHealingResult(
        root_cause_hypothesis=_sec("Root cause hypothesis")[:4000] or "See raw output.",
        severity=sev,
        user_visible_summary=_sec("User visible summary")[:4000] or "See raw markdown.",
        recommended_commands=cmds[:24],
        patch_plan=plans[:40],
        raw_markdown=raw[:24000],
    )
