# jarvis-api

FastAPI service for JARVIS. Phase 2 adds Ollama discovery, CrewAI orchestration (`POST /command`), SQLite memory, and agent status.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

See [../../docs/phase-2.md](../../docs/phase-2.md) for environment variables and troubleshooting.
