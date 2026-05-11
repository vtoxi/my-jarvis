"""Deterministic pseudo-embeddings when Ollama is unavailable or JARVIS_LLM_STUB is on."""

from __future__ import annotations

import hashlib
import math
from typing import Final

_DIM: Final[int] = 384


def deterministic_embedding(text: str, *, dim: int = _DIM) -> list[float]:
    """Reproducible unit vector from text (for tests and stub mode). Not semantic."""
    raw = (text or "").encode("utf-8")
    out: list[float] = []
    h = hashlib.sha256(raw).digest()
    i = 0
    while len(out) < dim:
        chunk = h + i.to_bytes(4, "big")
        h = hashlib.sha256(chunk).digest()
        for b in h:
            out.append((b / 255.0) * 2.0 - 1.0)
        i += 1
    vec = out[:dim]
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]
