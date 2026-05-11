from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal

from app.core.config import Settings

logger = logging.getLogger(__name__)

SiblingId = Literal["open_interpreter", "crewai"]


@dataclass
class _Running:
    popen: subprocess.Popen[str]
    cwd: Path
    cmd: str
    log_file: IO[str] | None = None
    log_path: Path | None = None


def jarvis_sibling_root(settings: Settings) -> Path:
    """Parent of `my-jarvis` repo (contains `open-interpreter`, `crewAI`, …)."""
    if settings.sibling_workspace_parent is not None:
        return Path(settings.sibling_workspace_parent).expanduser().resolve()
    # apps/api/app/services/this_file → parents[5] = jarvis/
    return Path(__file__).resolve().parents[5]


def resolve_open_interpreter_dir(settings: Settings) -> Path:
    if settings.open_interpreter_repo_path:
        return Path(settings.open_interpreter_repo_path).expanduser().resolve()
    return jarvis_sibling_root(settings) / "open-interpreter"


def resolve_crewai_dir(settings: Settings) -> Path:
    if settings.crewai_repo_path:
        return Path(settings.crewai_repo_path).expanduser().resolve()
    return jarvis_sibling_root(settings) / "crewAI"


class SiblingProcessManager:
    """Start/stop long-running commands in sibling repos (separate process groups)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._running: dict[SiblingId, _Running | None] = {"open_interpreter": None, "crewai": None}

    def _cmd_for(self, kind: SiblingId) -> str:
        if kind == "open_interpreter":
            return self.settings.open_interpreter_start_cmd.strip()
        return self.settings.crewai_start_cmd.strip()

    def _cwd_for(self, kind: SiblingId) -> Path:
        return resolve_open_interpreter_dir(self.settings) if kind == "open_interpreter" else resolve_crewai_dir(self.settings)

    def status(self) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for k in ("open_interpreter", "crewai"):
            r = self._running.get(k)  # type: ignore[arg-type]
            if not r:
                out[k] = {"running": False, "pid": None, "cwd": str(self._cwd_for(k)), "cmd": self._cmd_for(k)}
                continue
            code = r.popen.poll()
            if code is not None:
                if r.log_file is not None:
                    try:
                        r.log_file.flush()
                        r.log_file.close()
                    except OSError:
                        pass
                self._running[k] = None  # type: ignore[index]
                out[k] = {"running": False, "pid": None, "exit_code": code, "cwd": str(r.cwd), "cmd": r.cmd}
            else:
                out[k] = {"running": True, "pid": r.popen.pid, "cwd": str(r.cwd), "cmd": r.cmd}
        out["sandbox"] = bool(self.settings.automation_sandbox)
        return out

    def start(self, kind: SiblingId, *, cmd_override: str | None = None) -> dict[str, object]:
        if self.settings.automation_sandbox:
            return {"ok": False, "reason": "automation_sandbox", "message": "JARVIS_AUTOMATION_SANDBOX=true — no subprocess spawn."}

        st = self.status()[kind]
        if st.get("running"):
            return {"ok": False, "reason": "already_running", "pid": st.get("pid")}

        cwd = self._cwd_for(kind)
        if not cwd.is_dir():
            return {"ok": False, "reason": "repo_not_found", "path": str(cwd)}

        cmd = (cmd_override or "").strip() or self._cmd_for(kind)
        if not cmd:
            return {"ok": False, "reason": "empty_start_cmd", "message": f"Set JARVIS_{'OPEN_INTERPRETER' if kind == 'open_interpreter' else 'CREWAI'}_START_CMD"}

        argv = shlex.split(cmd)
        if not argv:
            return {"ok": False, "reason": "bad_cmd"}

        log_dir = self.settings.data_dir / "sibling_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{kind}.log"
        log_f: IO[str] | None = None
        try:
            log_f = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        except OSError as e:
            return {"ok": False, "reason": "log_open_failed", "detail": str(e)}

        env = os.environ.copy()
        if kind == "open_interpreter":
            env["INTERPRETER_HOST"] = str(self.settings.open_interpreter_server_host).strip()
            env["INTERPRETER_PORT"] = str(int(self.settings.open_interpreter_server_port))

        try:
            proc = subprocess.Popen(
                argv,
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                start_new_session=True,
            )
        except OSError as e:
            logger.warning("sibling start failed kind=%s: %s", kind, e)
            try:
                log_f.close()
            except OSError:
                pass
            return {"ok": False, "reason": "spawn_failed", "detail": str(e)}

        time.sleep(0.35)
        if proc.poll() is not None:
            exit_code = proc.returncode
            try:
                log_f.flush()
                log_f.close()
            except OSError:
                pass
            self._running[kind] = None  # type: ignore[index]
            tail = ""
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-3500:]
            except OSError:
                pass
            hint = (
                "Process exited immediately. For Open Interpreter without a terminal, use a command that includes "
                "`--server`, or run the REPL yourself in Terminal.app."
                if kind == "open_interpreter"
                else "Process exited immediately; check log_tail and command."
            )
            logger.warning("sibling exited immediately kind=%s code=%s", kind, exit_code)
            out: dict[str, object] = {
                "ok": False,
                "reason": "exited_immediately",
                "exit_code": exit_code,
                "log_file": str(log_path),
                "hint": hint,
                "log_tail": tail,
            }
            if kind == "open_interpreter":
                out["interpreter_url"] = (
                    f"http://{self.settings.open_interpreter_server_host}:{int(self.settings.open_interpreter_server_port)}"
                )
            return out

        self._running[kind] = _Running(popen=proc, cwd=cwd, cmd=cmd, log_file=log_f, log_path=log_path)
        logger.info("started sibling kind=%s pid=%s cwd=%s cmd=%s", kind, proc.pid, cwd, cmd)
        result: dict[str, object] = {
            "ok": True,
            "pid": proc.pid,
            "cwd": str(cwd),
            "cmd": cmd,
            "log_file": str(log_path),
        }
        if kind == "open_interpreter" and "--server" in cmd:
            result["interpreter_url"] = (
                f"http://{self.settings.open_interpreter_server_host}:{int(self.settings.open_interpreter_server_port)}"
            )
        return result

    def stop(self, kind: SiblingId, *, grace_s: float = 4.0) -> dict[str, object]:
        r = self._running.get(kind)  # type: ignore[arg-type]
        if not r:
            return {"ok": True, "message": "not_running"}

        pid = r.popen.pid
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._running[kind] = None  # type: ignore[index]
            if r.log_file is not None:
                try:
                    r.log_file.close()
                except OSError:
                    pass
            return {"ok": True, "message": "already_exited"}
        except PermissionError as e:
            return {"ok": False, "reason": "kill_permission", "detail": str(e)}

        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            if r.popen.poll() is not None:
                break
            time.sleep(0.1)
        if r.popen.poll() is None:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            r.popen.wait(timeout=5)

        self._running[kind] = None  # type: ignore[index]
        if r.log_file is not None:
            try:
                r.log_file.flush()
                r.log_file.close()
            except OSError:
                pass
        logger.info("stopped sibling kind=%s pid=%s", kind, pid)
        return {"ok": True, "pid": pid, "message": "terminated"}

    def stop_all(self) -> None:
        for k in ("open_interpreter", "crewai"):
            try:
                self.stop(k)  # type: ignore[arg-type]
            except Exception as e:
                logger.debug("stop_all %s: %s", k, e)
