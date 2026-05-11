from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    app_name: str = "JARVIS API"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    default_ollama_model: str = Field(default="llama3")
    data_dir: Path = Field(default=Path(".jarvis_data"))

    llm_stub: bool = Field(default=False, description="Deterministic /command without CrewAI or Ollama")
    crew_verbose: bool = Field(default=False)

    # Phase 3 — automation
    automation_sandbox: bool = Field(
        default=False,
        description="If true, log actions only; do not call Hammerspoon or interpreter subprocess",
    )
    hammerspoon_url: str = Field(default="http://127.0.0.1:17339")
    hammerspoon_token: str = Field(default="change-me-in-production", description="Bearer token for Hammerspoon HTTP bridge")

    interpreter_enabled: bool = Field(default=False, description="Allow bounded interpreter subprocess (off by default)")
    interpreter_safe_mode: bool = Field(default=True)
    interpreter_timeout_s: int = Field(default=45, ge=5, le=300)
    interpreter_python: str | None = Field(default=None, description="Python executable for interpreter CLI; defaults to sys.executable")

    # Phase 4 — Slack (read + analyze first; write gated later)
    slack_client_id: str = Field(default="", description="Slack app client ID for OAuth")
    slack_client_secret: str = Field(default="", description="Slack app client secret")
    slack_redirect_uri: str = Field(default="http://127.0.0.1:8000/slack/oauth/callback")
    slack_encryption_key: str | None = Field(
        default=None,
        description="Fernet key (urlsafe base64 32-byte). If unset, a dev key file is created under data_dir (not for production).",
    )
    slack_write_enabled: bool = Field(
        default=False,
        description="Phase 4C — allow chat.postMessage only with a valid signed approval token (never auto-send)",
    )
    slack_post_oauth_redirect: str = Field(
        default="http://127.0.0.1:5173/slack",
        description="Browser redirect after successful OAuth (desktop dev server)",
    )
    slack_approval_secret: str | None = Field(
        default=None,
        description="HMAC secret for /slack/send approval tokens; if unset, derived from client secret + encryption key",
    )

    # Phase 5 — screen intelligence (local-first; no cloud upload)
    screen_intel_enabled: bool = Field(default=True, description="Master switch for capture pipeline when endpoints are called")
    screen_capture_interval_s: float = Field(default=45.0, ge=5.0, le=600.0, description="Hint for passive polling; enforced client-side")
    screen_context_history_encrypt: bool = Field(
        default=True,
        description="Encrypt OCR/app snapshots in context_history.sqlite3 when a Fernet key is available",
    )
    screen_context_fernet_key: str | None = Field(
        default=None,
        description="Fernet key for context history; if unset, auto key under data_dir/screen/ (dev only)",
    )
    screen_max_capture_width: int = Field(default=1680, ge=640, le=3840, description="Downscale width for OCR to limit CPU")

    # Sibling repos (../open-interpreter, ../crewAI from my-jarvis) — start/stop via API
    sibling_workspace_parent: Path | None = Field(
        default=None,
        description="Directory containing my-jarvis + sibling repos; if unset, inferred from package path",
    )
    open_interpreter_repo_path: Path | None = Field(default=None, description="Override path to open-interpreter checkout")
    crewai_repo_path: Path | None = Field(default=None, description="Override path to crewAI checkout")
    open_interpreter_start_cmd: str = Field(
        default="poetry run interpreter --server",
        description=(
            "Shell-parsed argv from open-interpreter repo root. "
            "Use `--server` when launched from JARVIS (no TTY); plain `interpreter` exits immediately with stdin closed."
        ),
    )
    open_interpreter_server_host: str = Field(default="127.0.0.1", description="INTERPRETER_HOST for --server mode")
    open_interpreter_server_port: int = Field(
        default=8741,
        ge=1024,
        le=65534,
        description="INTERPRETER_PORT — avoid 8000 which conflicts with JARVIS API",
    )
    crewai_start_cmd: str = Field(
        default='uv run python -c "import threading; threading.Event().wait()"',
        description="Shell-parsed argv string run from crewAI repo root (override e.g. to a dev server)",
    )

    # Phase 6 — system evolution (local-first; mutations gated)
    system_patches_enabled: bool = Field(
        default=False,
        description="Allow POST /system/improve/apply after valid approval token (still requires clean git + repo root)",
    )
    system_patch_secret: str | None = Field(
        default=None,
        description="HMAC secret for patch/rollback approval tokens; derived from slack secret material if unset",
    )
    system_allow_subprocess: bool = Field(
        default=False,
        description="Allow ruff/mypy/pytest subprocesses for /system/audit when repo_root is set",
    )
    repo_root: Path | None = Field(
        default=None,
        description="Absolute path to git monorepo root (env: JARVIS_REPO_ROOT); required for audits/patches",
    )
    system_metrics_enabled: bool = Field(
        default=False,
        description="If true, attempt psutil for /system/performance (install psutil in the environment)",
    )
    system_log_max_bytes: int = Field(default=5_000_000, ge=100_000, le=50_000_000)
    system_log_backup_count: int = Field(default=3, ge=1, le=20)

    # Phase 8 — digital twin + idle learning (local-first; never silent autonomy)
    evolution_idle_enabled: bool = Field(
        default=True,
        description="Allow POST /evolution/idle (and scheduled ticks when enabled) to run bounded idle learning",
    )
    evolution_idle_schedule_enabled: bool = Field(
        default=False,
        description="If true, start an asyncio background loop that runs idle learning every interval (opt-in)",
    )
    evolution_idle_schedule_interval_s: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Seconds between scheduled idle learning ticks (min 5m, max 24h)",
    )
    evolution_knowledge_enabled: bool = Field(
        default=True,
        description="Local SQLite knowledge chunks + optional Ollama embeddings for /evolution/knowledge/*",
    )
    evolution_knowledge_embed_model: str = Field(
        default="",
        description="Ollama model for embeddings; empty uses default_ollama_model",
    )
    evolution_knowledge_search_max_rows: int = Field(
        default=800,
        ge=50,
        le=5000,
        description="Max recent chunks scanned per similarity search (local-first cap)",
    )


settings = Settings()
