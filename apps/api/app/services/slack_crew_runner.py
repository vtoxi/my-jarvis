from __future__ import annotations

import logging
from dataclasses import dataclass

from crewai import Agent, Crew, LLM, Process, Task

from app.agents import response_draft_agent as draft_defs
from app.agents import slack_intel_agent as intel_defs
from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SlackBriefingCrewResult:
    briefing_markdown: str
    draft_hints_markdown: str


def _stub_briefing(corpus: str) -> SlackBriefingCrewResult:
    clip = (corpus or "").strip()
    if len(clip) > 1200:
        clip = clip[:1199] + "…"
    body = (
        "## Today's Command Brief\n\n"
        "### Urgent Slack\n"
        "_Stub mode (`JARVIS_LLM_STUB`) — connect Ollama for live analysis._\n"
        "Evidence excerpt:\n\n"
        f"```\n{clip}\n```\n\n"
        "### Important Mentions\n"
        "- (not analyzed in stub)\n\n"
        "### Pending Reviews\n"
        "- (not analyzed in stub)\n\n"
        "### Suggested Priorities\n"
        "1. Disable stub and re-run briefing with a connected workspace.\n\n"
        "### Risks\n"
        "- Intelligence offline; operator confirmation required.\n"
    )
    hints = (
        "## Suggested reply themes (draft-only, not sent)\n"
        "- Acknowledge receipt and propose a concrete next step with a time boundary.\n"
        "- For blockers: restate impact + owner + ask for decision.\n"
    )
    return SlackBriefingCrewResult(briefing_markdown=body, draft_hints_markdown=hints)


def _stub_draft(context: str, tone: str) -> str:
    return (
        f"## Draft ({tone}) — stub mode\n\n"
        "_No model call — enable Ollama or disable `JARVIS_LLM_STUB`._\n\n"
        "### Draft A\n"
        f"Thanks for the context. I’m on it and will circle back with an update.\n\n"
        f"_Context digest:_\n```\n{(context or '')[:800]}\n```\n"
    )


def run_slack_briefing_crew(*, settings: Settings, corpus: str, model: str) -> SlackBriefingCrewResult:
    if settings.llm_stub:
        return _stub_briefing(corpus)

    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.15,
    )

    intel = Agent(
        role=intel_defs.SLACK_INTEL_ROLE,
        goal=intel_defs.SLACK_INTEL_GOAL,
        backstory=intel_defs.SLACK_INTEL_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=5,
    )
    drafter = Agent(
        role=draft_defs.RESPONSE_DRAFT_ROLE,
        goal=draft_defs.RESPONSE_DRAFT_GOAL,
        backstory=draft_defs.RESPONSE_DRAFT_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=4,
    )

    intel_task = Task(
        description=(
            "You are given raw Slack evidence (recent messages). Do not fabricate messages.\n\n"
            f"### Evidence\n{corpus}\n\n"
            "Produce markdown with EXACTLY these sections and headings:\n"
            "## Today's Command Brief\n"
            "### Urgent Slack\n"
            "### Important Mentions\n"
            "### Pending Reviews\n"
            "### Suggested Priorities\n"
            "### Risks\n\n"
            "Use bullets. Quantify where the evidence supports it (e.g. '3 threads'). "
            "Call out deadlines, blockers, and exec/VIP signals if visible in text."
        ),
        expected_output="Markdown brief with the requested section headings.",
        agent=intel,
    )

    draft_task = Task(
        description=(
            "Using ONLY the Slack Intelligence Analyst task output available in your context "
            "(do not invent messages), append a new section titled exactly:\n"
            "## Suggested reply themes (draft-only, not sent)\n"
            "Give 2–4 short bullet themes the operator could turn into Slack replies. "
            "No wording that implies a message was already sent."
        ),
        expected_output="Markdown including the suggested reply themes section.",
        agent=drafter,
        context=[intel_task],
    )

    crew = Crew(
        agents=[intel, drafter],
        tasks=[intel_task, draft_task],
        process=Process.sequential,
        verbose=settings.crew_verbose,
    )
    logger.info("slack briefing crew kickoff model=ollama/%s", tag)
    crew.kickoff()

    def _task_text(task: object) -> str:
        try:
            out = getattr(task, "output", None)
            if out is None:
                return ""
            return str(getattr(out, "raw", out))
        except Exception:
            return ""

    brief = _task_text(intel_task).strip()
    hints = _task_text(draft_task).strip()
    if not brief:
        brief = "_No briefing output._"
    if not hints:
        hints = "_No draft hints._"
    return SlackBriefingCrewResult(briefing_markdown=brief, draft_hints_markdown=hints)


def run_slack_draft_crew(*, settings: Settings, context: str, tone: str, model: str) -> str:
    if settings.llm_stub:
        return _stub_draft(context, tone)

    tag = model.removeprefix("ollama/").strip() or settings.default_ollama_model
    llm = LLM(
        model=f"ollama/{tag}",
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0.25,
    )
    drafter = Agent(
        role=draft_defs.RESPONSE_DRAFT_ROLE,
        goal=draft_defs.RESPONSE_DRAFT_GOAL,
        backstory=draft_defs.RESPONSE_DRAFT_BACKSTORY,
        llm=llm,
        verbose=settings.crew_verbose,
        max_iter=4,
    )
    task = Task(
        description=(
            f"Tone: **{tone}** (executive | friendly | technical).\n"
            "Draft Slack-ready reply OPTIONS for human approval only. "
            "Do not state that a message was sent.\n\n"
            f"### Context\n{context}\n\n"
            "Output markdown with '### Option A' and optional '### Option B'. Keep under ~120 words each."
        ),
        expected_output="Markdown reply drafts.",
        agent=drafter,
    )
    crew = Crew(agents=[drafter], tasks=[task], process=Process.sequential, verbose=settings.crew_verbose)
    logger.info("slack draft crew kickoff model=ollama/%s", tag)
    raw = crew.kickoff()
    out = str(raw).strip()
    if not out and task.output is not None:
        out = str(getattr(task.output, "raw", task.output)).strip()
    return out or "_No draft output._"
