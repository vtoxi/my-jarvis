from typing import Annotated

from fastapi import Request

from app.core.automation_state import AutomationState
from app.memory.store import MemoryStore
from app.services.hammerspoon_service import HammerspoonService
from app.services.ollama_client import OllamaClient


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


def get_memory(request: Request) -> MemoryStore:
    return request.app.state.memory


def get_automation(request: Request) -> AutomationState:
    return request.app.state.automation


def get_hammerspoon(request: Request) -> HammerspoonService:
    return request.app.state.hammerspoon


OllamaDep = Annotated[OllamaClient, get_ollama]
MemoryDep = Annotated[MemoryStore, get_memory]
