from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class InterpreterResult:
    ok: bool
    action_plan: list[dict[str, Any]] | None
    raw_stdout: str
    error: str | None


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and "steps" in data and isinstance(data["steps"], list):
            return [x for x in data["steps"] if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    return None


def run_interpreter_for_plan(*, settings: Settings, user_prompt: str) -> InterpreterResult:
    if not settings.interpreter_enabled:
        return InterpreterResult(
            ok=False,
            action_plan=None,
            raw_stdout="",
            error="Interpreter disabled (set JARVIS_INTERPRETER_ENABLED=true after installing interpreter)",
        )

    exe = settings.interpreter_python or sys.executable
    if shutil.which("interpreter") is None and exe == sys.executable:
        # try module form
        cmd = [exe, "-m", "interpreter", "--help"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        except Exception:
            pass

    cli = shutil.which("interpreter")
    if cli:
        cmd = [cli, "--help"]
    else:
        cmd = [exe, "-m", "interpreter"]

    system = (
        "You output ONLY a JSON array of steps. No prose. Schema per element: "
        '{"type":"open_app|open_url|focus|delay","target":"<bundle keyword or url or ms>","tier":"safe|confirm|restricted"}. '
        "Never emit shell commands."
    )
    script = json.dumps(
        {
            "system": system,
            "prompt": user_prompt,
        },
    )
    # Many versions lack stable non-interactive flags; run with stdin closed quickly and expect failure with guidance
    try:
        proc = subprocess.run(
            [*cmd, "--version"] if cli else [exe, "-m", "interpreter", "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        logger.debug("interpreter version probe rc=%s out=%s", proc.returncode, proc.stdout[:200])
    except FileNotFoundError:
        return InterpreterResult(
            ok=False,
            action_plan=None,
            raw_stdout="",
            error="interpreter CLI not found; pip install open-interpreter or use workflow profiles only",
        )
    except subprocess.TimeoutExpired:
        return InterpreterResult(ok=False, action_plan=None, raw_stdout="", error="interpreter version probe timed out")

    # Phase 3 bounded path: do not run unconstrained interpreter; return structured hint
    return InterpreterResult(
        ok=False,
        action_plan=None,
        raw_stdout="",
        error=(
            "Open Interpreter is gated in Phase 3: enable JARVIS_INTERPRETER_ENABLED and install `interpreter` CLI; "
            "until then, use /workflows/run with Hammerspoon profiles or pass an explicit JSON ActionPlan to POST /execute."
        ),
    )


def plan_from_json_text(text: str) -> list[dict[str, Any]] | None:
    return _extract_json_array(text)
