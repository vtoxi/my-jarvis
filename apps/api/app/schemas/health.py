from pydantic import BaseModel, Field


class OllamaHealth(BaseModel):
    reachable: bool = Field(description="Whether Ollama /api/tags responded successfully")
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    ollama: OllamaHealth | None = None


class VersionResponse(BaseModel):
    version: str
    service: str
