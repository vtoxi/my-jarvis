from pydantic import BaseModel, Field


class OllamaModelInfo(BaseModel):
    name: str
    size: int | None = None
    modified_at: str | None = None


class ModelsResponse(BaseModel):
    ollama_reachable: bool
    ollama_error: str | None = None
    active_model: str
    installed: list[OllamaModelInfo] = Field(default_factory=list)
    recommended_defaults: list[str] = Field(default_factory=lambda: ["llama3", "qwen2.5-coder"])
