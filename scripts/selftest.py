#!/usr/bin/env python3
"""Fast offline regression tests for the research engine.

Runs before any long network collection in GitHub Actions, so deterministic
coding errors are caught in seconds instead of after a 10-20 minute crawl.
"""
from __future__ import annotations
import importlib.util
import json
import pathlib
import sys
import types

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    class _OfflineSession:
        def __init__(self): self.headers = {}
    sys.modules["requests"] = types.SimpleNamespace(Session=_OfflineSession)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("westcon_research", ROOT / "scripts/research.py")
research = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(research)

assert research.clamp(-3) == 0
assert research.clamp(101) == 100
assert research.clamp(49.6) == 50

sample = [{
    "id": "selftest-proc-1",
    "evidenceType": "procurement",
    "country": "ES",
    "technologyMatches": [{"id": "cybersecurity", "themeIds": ["secops"]}],
    "awardedValue": 1_000_000,
    "buyer": "Organismo Público de Prueba",
    "winner": "Integrador de Prueba",
    "winners": ["Integrador de Prueba"],
    "vendor": "Palo Alto Networks",
    "sector": "Administración Pública",
    "published": "2026-08-01",
}]
rows = research.procurement_market_aggregate(sample)
assert len(rows) == 1
assert rows[0]["country"] == "ES"
assert rows[0]["technologyId"] == "cybersecurity"
assert 0 <= rows[0]["demandIndex"] <= 100

# Exercise the same late-stage pure functions that run after the long crawl.
current = json.loads((ROOT / "data/research.latest.json").read_text(encoding="utf-8"))
evidence = current.get("evidence", [])
channels = current.get("channelSignals", [])
integrators = current.get("integratorSignals", [])
customers = current.get("customerSignals", [])
coverage = research.vendor_coverage(evidence, channels, integrators, customers)
assert isinstance(coverage, list)
assert isinstance(research.research_gaps(coverage), list)
assert isinstance(research.signal_stats(evidence), dict)
assert isinstance(research.procurement_market_aggregate(evidence), list)

print("OK · research engine offline self-test")
