"""Reject obvious website navigation and illustration labels as vendor *names*.

This is an exact, auditable denylist, not a guess based on text capitalisation.
It never alters the archived source trail. Candidate discovery and the public
projection consult the same policy to stop legacy noise becoming green claims.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .model import canonical
from .storage import read_json


@lru_cache(maxsize=1)
def _non_vendor_labels() -> dict[str, str]:
    registry = read_json("config/current/non_vendor_labels.json", {})
    return {
        canonical(label): category
        for category, values in (registry.get("categories") or {}).items()
        for label in values
        if isinstance(label, str) and canonical(label)
    }


_ASSET_NAME = re.compile(r"(?i)\.(?:svg|png|jpe?g|webp|gif|ico|avif)(?:\?.*)?$")
_ICON_LABEL = re.compile(r"(?i)^(?:(?:icon|logo|image|imagen|banner)[\s_-]+|.+\s+(?:icon|logo))$")


def non_vendor_reason(value: str) -> str | None:
    """Return an objective exclusion reason, or None for a plausible name."""
    raw = str(value or "").strip()
    if not raw:
        return "empty"
    if _ASSET_NAME.search(raw):
        return "asset_filename"
    if _ICON_LABEL.fullmatch(raw):
        return "illustration_label"
    return _non_vendor_labels().get(canonical(raw))


def plausible_vendor_name(value: str) -> bool:
    return non_vendor_reason(value) is None
