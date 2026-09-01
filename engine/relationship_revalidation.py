"""Relationship-level historical provenance revalidation for v4.0.5 source-r5."""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config/current/relationship_revalidation_registry.json"

HISTORICAL_KINDS = {
    "HISTORICAL_RECOVERED",
    "ARCHIVE_RECOVERED",
    "ARCHIVE_CORROBORATION",
    "REPORT_CORROBORATION",
    "LEGACY_UNRESOLVED",
}


def _historical(ev: Mapping[str, Any]) -> bool:
    return str(ev.get("provenance_origin") or "").upper() in HISTORICAL_KINDS


def _current_open(ev: Mapping[str, Any]) -> bool:
    return (
        not _historical(ev)
        and str(ev.get("url") or "").startswith(("http://", "https://"))
    )


def relation_key(rel: Mapping[str, Any]) -> str:
    countries = sorted(str(x) for x in (rel.get("countries") or []))
    raw = "|".join([
        str(rel.get("entity_a_id") or rel.get("entity_a") or "").casefold(),
        str(rel.get("relation") or "").casefold(),
        str(rel.get("entity_b_id") or rel.get("entity_b") or "").casefold(),
        ",".join(countries).casefold(),
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _client_section(data: Mapping[str, Any], entity_id: Any, entity_name: Any) -> str:
    for section in ("clients_public", "clients_private"):
        for row in data.get(section) or []:
            if (
                str(row.get("id") or "") == str(entity_id or "")
                or str(row.get("name") or "") == str(entity_name or "")
            ):
                return section
    return "clients_public"


def build_registry(
    baseline_graph: Mapping[str, Any],
    current_graph: Mapping[str, Any],
    intelligence: Mapping[str, Any],
    *,
    baseline_source: str = "",
) -> dict[str, Any]:
    current_keys = {
        relation_key(rel)
        for rel in current_graph.get("relationships") or []
        if isinstance(rel, Mapping)
    }
    candidates = []
    for rel in baseline_graph.get("relationships") or []:
        if not isinstance(rel, Mapping):
            continue
        evidence = [ev for ev in rel.get("evidence") or [] if isinstance(ev, Mapping)]
        historical = [ev for ev in evidence if _historical(ev)]
        current = [ev for ev in evidence if _current_open(ev)]
        if not historical or current:
            continue
        key = relation_key(rel)
        if key in current_keys:
            continue

        seeds = []
        seen = set()
        for ev in historical:
            url = str(ev.get("url") or "").strip()
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            seeds.append({
                "url": url,
                "official": bool(ev.get("official")),
                "source_grade": str(ev.get("source_grade") or ("A" if ev.get("official") else "B")),
                "source_name": str(ev.get("source") or ev.get("title") or "Fuente histórica"),
                "source_type": str(ev.get("source_type") or ""),
            })

        candidates.append({
            "id": f"relation-h:{key}",
            "key": key,
            "section": _client_section(
                intelligence, rel.get("entity_a_id"), rel.get("entity_a")
            ),
            "entity": rel.get("entity_a"),
            "entity_id": rel.get("entity_a_id"),
            "relation": rel.get("relation"),
            "entity_b": rel.get("entity_b"),
            "entity_b_id": rel.get("entity_b_id"),
            "countries": rel.get("countries") or [],
            "country": rel.get("country"),
            "status_before": rel.get("status"),
            "confidence_before": rel.get("confidence"),
            "historical_evidence": historical,
            "revalidation_seeds": seeds,
            "revalidation_status": "search-required",
            "revalidated_evidence": [],
            "last_checked_at": None,
            "last_error": "",
        })

    return {
        "version": "4.0.5",
        "policy": (
            "Las relaciones H se conservan como deuda de revalidación. "
            "No cuentan como acreditadas hasta tener fuente abierta actual."
        ),
        "baseline_graph": baseline_source,
        "candidates_total": len(candidates),
        "supported_current_open": 0,
        "search_required": len(candidates),
        "candidates": candidates,
    }


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"version": "4.0.5", "candidates_total": 0, "supported_current_open": 0, "search_required": 0, "candidates": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))


def save_registry(registry: Mapping[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def relationship_revalidation_debt(state_gaps: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    state_gaps = state_gaps or {}
    registry = load_registry()
    debt = []
    for row in registry.get("candidates") or []:
        if row.get("revalidation_status") == "supported-by-current-open-source":
            continue
        history = state_gaps.get(row.get("id")) or {}
        debt.append({
            "id": row.get("id"),
            "section": row.get("section") or "clients_public",
            "entity": row.get("entity"),
            "entity_id": row.get("entity_id"),
            "field": "technology_signal",
            "country_context": row.get("country") or ",".join(row.get("countries") or []),
            "research_state": "Por investigar",
            "priority": 1,
            "reason": "relación histórica derivada pendiente de revalidación con fuente abierta actual",
            "gap_kind": "historical-relationship-revalidation",
            "target_level": "relationship",
            "target_values": [row.get("entity_b")] if row.get("entity_b") else [],
            "relation": row.get("relation"),
            "entity_b": row.get("entity_b"),
            "entity_b_id": row.get("entity_b_id"),
            "revalidation_seeds": row.get("revalidation_seeds") or [],
            "attempts_completed": int(history.get("attempts") or 0),
            "accepted_evidences": int(history.get("accepted") or 0),
            "consecutive_no_yield": int(history.get("consecutive_no_yield") or 0),
            "next_pass": int(history.get("next_pass") or 1),
            "next_due_at": history.get("next_due_at"),
            "last_attempt_at": history.get("last_attempt_at"),
            "last_error": history.get("last_error") or "",
            "close_policy": (
                "La relación no se acredita por H. Debe confirmarse con una fuente "
                "abierta actual para el mismo cliente y señal tecnológica."
            ),
            "strategy_profile": "historical-relationship-open-source-revalidation",
            "retry_policy": "persistent-backoff-with-circuit-breaker",
        })
    return debt


def _plain_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def _canon(value: Any) -> str:
    text = str(value or "").casefold()
    text = text.translate(str.maketrans("áéíóúüñç", "aeiouunc"))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _target_match(target: Any, text: str) -> bool:
    wanted = _canon(target)
    hay = _canon(text)
    if not wanted:
        return False
    if len(wanted) <= 4:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(wanted)}(?![a-z0-9])", hay))
    return wanted in hay


def revalidate_registry(max_runtime: int = 300, max_items: int | None = None) -> dict[str, Any]:
    registry = load_registry()
    start = time.monotonic()
    checked = supported = failed = 0
    headers = {
        "User-Agent": "Westcon-Iberia-Decision-Intelligence/4.0.5 (+open-source revalidation)"
    }

    pending = [
        row for row in registry.get("candidates") or []
        if row.get("revalidation_status") != "supported-by-current-open-source"
    ]
    if max_items is not None:
        pending = pending[:max_items]

    for row in pending:
        if time.monotonic() - start >= max_runtime:
            break
        checked += 1
        target = row.get("entity_b")
        matched = False
        errors = []
        for seed in row.get("revalidation_seeds") or []:
            url = str(seed.get("url") or "")
            if not url.startswith(("http://", "https://")):
                continue
            try:
                response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
                response.raise_for_status()
                body = _plain_text(response.text)
                if _target_match(target, body):
                    evidence = {
                        "source": seed.get("source_name") or urlparse(url).netloc,
                        "title": f"Revalidación actual de {target}",
                        "url": response.url,
                        "date": time.strftime("%Y-%m-%d"),
                        "description": (
                            f"Fuente abierta actual reconsultada; contiene el objetivo "
                            f"de relación '{target}'."
                        ),
                        "source_type": (
                            "official-procurement-notice-revalidated"
                            if seed.get("official")
                            else "public-web-revalidated"
                        ),
                        "source_grade": "A" if seed.get("official") else "B",
                        "official": bool(seed.get("official")),
                        "provenance_origin": "PUBLIC_PRIMARY" if seed.get("official") else "PUBLIC_SECONDARY",
                        "intelligence_tier": "A2" if seed.get("official") else "C",
                        "source_role": (
                            "Fuente primaria externa"
                            if seed.get("official")
                            else "Fuente abierta secundaria"
                        ),
                    }
                    row["revalidation_status"] = "supported-by-current-open-source"
                    row["revalidated_evidence"] = [evidence]
                    row["last_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    row["last_error"] = ""
                    supported += 1
                    matched = True
                    break
            except Exception as exc:
                errors.append(f"{url}: {exc}")

        if not matched:
            row["last_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            row["last_error"] = " | ".join(errors)[:1000]
            failed += 1

    registry["candidates_total"] = len(registry.get("candidates") or [])
    registry["supported_current_open"] = sum(
        1 for row in registry.get("candidates") or []
        if row.get("revalidation_status") == "supported-by-current-open-source"
    )
    registry["search_required"] = (
        registry["candidates_total"] - registry["supported_current_open"]
    )
    save_registry(registry)

    return {
        "checked": checked,
        "supported": supported,
        "not_yet_supported": failed,
        "supported_total": registry["supported_current_open"],
        "search_required": registry["search_required"],
    }
