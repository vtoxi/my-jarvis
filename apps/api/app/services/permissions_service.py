from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

# Known bundle IDs for workflow targets (expand over time)
BUNDLE_BY_APP: dict[str, str] = {
    "slack": "com.tinyspeck.slackmacgap",
    "cursor": "com.todesktop.230313mzl4w4u92",
    "mail": "com.apple.mail",
    "calendar": "com.apple.iCal",
    "notes": "com.apple.Notes",
    "zoom": "us.zoom.xos",
    "terminal": "com.apple.Terminal",
    "safari": "com.apple.Safari",
    "chrome": "com.google.Chrome",
    "github": "com.github.GitHubClient",
    "cursor ide": "com.todesktop.230313mzl4w4u92",
}


class RiskTier(str, Enum):
    safe = "safe"
    confirm = "confirm"
    restricted = "restricted"


RESTRICTED_PATTERNS = (
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bdefaults\s+write\b",
    r"\bchmod\s+777\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bcsrutil\b",
    r"\bkillall\s+",
)


@dataclass
class NormalizedStep:
    type: str
    target: str
    tier: RiskTier
    bundle_id: str | None
    meta: dict[str, Any]


def _resolve_bundle(target: str) -> str | None:
    key = target.strip().lower()
    if key in BUNDLE_BY_APP:
        return BUNDLE_BY_APP[key]
    if "." in target and not target.startswith("http") and "/" not in target:
        # assume literal bundle id
        return target.strip()
    return None


def _classify_url(url: str) -> RiskTier:
    try:
        p = urlparse(url)
    except Exception:
        return RiskTier.restricted
    if p.scheme not in ("http", "https"):
        return RiskTier.restricted
    return RiskTier.safe


def _classify_shellish(text: str) -> RiskTier:
    t = text.lower()
    for pat in RESTRICTED_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return RiskTier.restricted
    if any(x in t for x in ("delete", "unlink", "truncate", "format disk", "> /dev/", "curl|sh")):
        return RiskTier.confirm
    return RiskTier.safe


def classify_step(step_type: str, target: str) -> NormalizedStep:
    st = step_type.strip().lower()
    tgt = (target or "").strip()
    bundle: str | None = None

    if st == "open_url":
        tier = _classify_url(tgt)
        return NormalizedStep(type=st, target=tgt, tier=tier, bundle_id=None, meta={})

    if st in ("open_app", "focus"):
        bundle = _resolve_bundle(tgt)
        if bundle:
            return NormalizedStep(
                type=st,
                target=tgt,
                tier=RiskTier.safe,
                bundle_id=bundle,
                meta={"resolved_bundle": bundle},
            )
        # unknown app name — require confirmation
        return NormalizedStep(type=st, target=tgt, tier=RiskTier.confirm, bundle_id=None, meta={})

    if st == "delay":
        if not tgt.isdigit():
            return NormalizedStep(type=st, target=tgt, tier=RiskTier.confirm, bundle_id=None, meta={})
        return NormalizedStep(type=st, target=tgt, tier=RiskTier.safe, bundle_id=None, meta={"ms": int(tgt)})

    if st == "tile_preset":
        return NormalizedStep(type=st, target=tgt, tier=RiskTier.confirm, bundle_id=None, meta={})

    # unknown step types default to confirm
    tier = _classify_shellish(tgt)
    return NormalizedStep(type=st, target=tgt, tier=tier, bundle_id=bundle, meta={})


def evaluate_plan(steps: list[dict[str, Any]]) -> tuple[list[NormalizedStep], list[str]]:
    errors: list[str] = []
    normalized: list[NormalizedStep] = []
    for i, raw in enumerate(steps):
        st = str(raw.get("type", "")).strip()
        tgt = str(raw.get("target", "")).strip()
        declared = raw.get("tier")
        if not st or not tgt:
            errors.append(f"step {i}: missing type or target")
            continue
        ns = classify_step(st, tgt)
        if isinstance(declared, str):
            try:
                override = RiskTier(declared)
                if override == RiskTier.restricted:
                    ns = NormalizedStep(
                        type=ns.type,
                        target=ns.target,
                        tier=RiskTier.restricted,
                        bundle_id=ns.bundle_id,
                        meta={**ns.meta, "overridden": True},
                    )
                elif override == RiskTier.confirm and ns.tier == RiskTier.safe:
                    ns = NormalizedStep(
                        type=ns.type,
                        target=ns.target,
                        tier=RiskTier.confirm,
                        bundle_id=ns.bundle_id,
                        meta={**ns.meta, "overridden": True},
                    )
            except ValueError:
                pass
        normalized.append(ns)
        if ns.tier == RiskTier.restricted:
            errors.append(f"step {i}: restricted action blocked ({ns.type} → {ns.target})")
    return normalized, errors


def needs_confirmation(steps: list[NormalizedStep]) -> bool:
    return any(s.tier == RiskTier.confirm for s in steps)
