from __future__ import annotations

from typing import Any

STATIC_AGENTS: list[dict[str, Any]] = [
    {
        "id": "commander",
        "name": "Commander",
        "phase": 2,
        "enabled": True,
        "description": "Primary routing and user-facing intelligence",
    },
    {
        "id": "planner",
        "name": "Planner",
        "phase": 2,
        "enabled": True,
        "description": "Executive planning and daily brief scaffolding",
    },
    {
        "id": "slack",
        "name": "Slack Agent",
        "phase": 4,
        "enabled": True,
        "description": "Slack intelligence, briefing, and draft-only reply rail",
    },
    {
        "id": "interpreter",
        "name": "Interpreter Agent",
        "phase": 3,
        "enabled": True,
        "description": "Bounded Open Interpreter path (gated; JSON plans only)",
    },
    {
        "id": "executor",
        "name": "Execution Officer",
        "phase": 3,
        "enabled": True,
        "description": "Hammerspoon + workflow execution rail",
    },
    {
        "id": "context_observer",
        "name": "Context Analyst",
        "phase": 5,
        "enabled": True,
        "description": "Foreground app + OCR situational read",
    },
    {
        "id": "productivity_copilot",
        "name": "Productivity Copilot",
        "phase": 5,
        "enabled": True,
        "description": "Strategic next moves from on-screen evidence",
    },
    {
        "id": "self_healing",
        "name": "Self-Healing Analyst",
        "phase": 6,
        "enabled": True,
        "description": "Diagnose health signals and propose approval-gated repairs",
    },
    {
        "id": "code_audit",
        "name": "Code Audit Lead",
        "phase": 6,
        "enabled": True,
        "description": "Synthesize static analysis and technical debt narratives",
    },
]
