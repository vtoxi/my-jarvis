"""Optional CrewAI path for natural-language → ActionPlan (future: wire to POST /execute)."""

from __future__ import annotations

# Intentionally minimal in Phase 3: use /permissions/check + explicit JSON steps or workflow profiles.
# Import crew here only when expanding NL execution with the same LLM stack as jarvis_crew.
