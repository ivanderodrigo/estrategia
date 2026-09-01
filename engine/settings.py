"""Canonical runtime settings for Westcon Iberia Decision Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
RESEARCH_POLICY = json.loads(
    (ROOT / "config/current/research_policy.json").read_text(encoding="utf-8")
)

SECTIONS = (
    "manufacturers",
    "distributors",
    "integrators",
    "clients_public",
    "clients_private",
    "trends",
    "architectures",
)


@dataclass(frozen=True)
class ResearchProfile:
    """Bounded research workload used by both CLI and GitHub Actions."""

    entity_limit: int
    pages_per_entity: int
    request_timeout_s: int
    retries: int
    cache_ttl_s: int
    ted_lookback_days: int
    checkpoint_every: int


def _profile(name: str, defaults: tuple[int, int, int, int, int, int, int]) -> ResearchProfile:
    configured = (RESEARCH_POLICY.get("profiles") or {}).get(name) or {}
    keys = (
        "entity_limit", "pages_per_entity", "request_timeout_s", "retries",
        "cache_ttl_s", "ted_lookback_days", "checkpoint_every",
    )
    values = [int(configured.get(key, default)) for key, default in zip(keys, defaults)]
    return ResearchProfile(*values)


RESEARCH_PROFILES = {
    "daily": _profile("daily", (120, 5, 7, 2, 21_600, 10, 20)),
    "deep": _profile("deep", (520, 16, 9, 3, 86_400, 35, 20)),
    "exhaustive": _profile("exhaustive", (1_400, 32, 12, 4, 172_800, 100, 15)),
}
