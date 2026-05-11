from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_agents,
    routes_command,
    routes_health,
    routes_memory,
    routes_models,
    routes_phase3,
    routes_phase5,
    routes_sibling_projects,
    routes_slack,
    routes_system,
)
from app.core.automation_state import AutomationState
from app.core.screen_intel_state import ScreenIntelState
from app.core.config import settings
from app.core.logging import configure_logging
from app.memory.context_history_store import ContextHistoryStore
from app.memory.store import MemoryStore
from app.services.hammerspoon_service import HammerspoonService
from app.services.ollama_client import OllamaClient
from app.services.sibling_projects_service import SiblingProcessManager
from app.services.system_evolution_store import SystemEvolutionStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log_path = configure_logging(settings)
    app.state.api_log_path = log_path
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "logs").mkdir(parents=True, exist_ok=True)
    db_path = settings.data_dir / "memory.sqlite3"
    memory = MemoryStore(db_path)
    await memory.setup()
    app.state.memory = memory
    app.state.ollama = OllamaClient(settings.ollama_base_url)
    app.state.automation = AutomationState()
    app.state.hammerspoon = HammerspoonService(settings)
    app.state.slack_oauth_states = {}
    app.state.screen_intel = ScreenIntelState(capture_interval_s=float(settings.screen_capture_interval_s))
    ctx_db = settings.data_dir / "context_history.sqlite3"
    context_history = ContextHistoryStore(ctx_db, settings)
    await context_history.setup()
    app.state.context_history = context_history
    sibling_mgr = SiblingProcessManager(settings)
    app.state.sibling_projects = sibling_mgr
    evolution = SystemEvolutionStore(settings)
    await evolution.setup()
    app.state.system_evolution = evolution
    yield
    sibling_mgr.stop_all()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_health.router)
    app.include_router(routes_models.router)
    app.include_router(routes_command.router)
    app.include_router(routes_agents.router)
    app.include_router(routes_memory.router)
    app.include_router(routes_phase3.router)
    app.include_router(routes_slack.router)
    app.include_router(routes_phase5.router)
    app.include_router(routes_sibling_projects.router)
    app.include_router(routes_system.router)
    return app


app = create_app()
