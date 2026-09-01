"""Canonical build pipeline with transactional publication."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .enrichment import (
    apply_curated,
    apply_curated_distributors,
    derive_overlap_fields,
    derive_secondary_views,
    normalize_fields,
    project_graph_to_views,
)
from .gaps import build_gaps
from .client_intelligence import derive_client_intelligence
from .knowledge_provenance import (
    apply_westcon_document_provenance,
    load_knowledge_baseline,
    mark_legacy_unresolved,
    provenance_summary,
    restore_protected_knowledge,
    sync_document_sources,
)
from .graph import build_graph
from .metrics import calculate
from .publication import public_payloads
from .quality import audit
from .settings import SECTIONS, VERSION
from .storage import atomic_write_many, json_bytes, read_json


def _sync_source_catalog(data: dict[str, Any]) -> None:
    catalog = list(data.get("source_catalog") or [])
    seen = {
        str(item.get("url") or "")
        for item in catalog
        if isinstance(item, dict) and item.get("url")
    }
    for section in SECTIONS:
        for row in data.get(section) or []:
            for field in (row.get("fields") or {}).values():
                evidence_rows = list(field.get("evidence") or [])
                for item in field.get("items") or []:
                    if isinstance(item, dict):
                        evidence_rows.extend(item.get("evidence") or [])
                for evidence in evidence_rows:
                    if not isinstance(evidence, dict):
                        continue
                    url = str(evidence.get("url") or "")
                    if not url.startswith(("http://", "https://")) or url in seen:
                        continue
                    seen.add(url)
                    catalog.append({
                        "name": evidence.get("source") or evidence.get("title") or "Fuente pública",
                        "class": evidence.get("source_type") or "public-web",
                        "scope": [evidence.get("scope") or "GLOBAL"],
                        "dimensions": [section],
                        "url": url,
                    })
    data["source_catalog"] = catalog


def run() -> dict[str, Any]:
    data = read_json("data/current/intelligence.json")
    knowledge_baseline = load_knowledge_baseline()
    restore_protected_knowledge(data, knowledge_baseline)
    apply_westcon_document_provenance(data)
    mark_legacy_unresolved(data)
    research_state = read_json("data/current/research_state.json", {})
    if not isinstance(research_state, dict):
        research_state = {}
    research_state["version"] = VERSION
    ledger = read_json("data/current/research_ledger.json", {})
    now = datetime.now(timezone.utc).isoformat()

    meta = data.setdefault("meta", {})
    meta["version"] = VERSION
    meta["generated_at"] = now
    meta["principle"] = "Hipersofisticada por dentro. Extremadamente sencilla por fuera."
    meta["research_engine"] = {
        "version": VERSION,
        "pipeline": [
            "source-registry", "health-check", "discover", "fetch", "extract",
            "validate", "item-provenance", "graph", "gap", "learn", "publish",
        ],
        "success_definition": (
            "Una descarga correcta no equivale a inteligencia: se miden evidencias nuevas, "
            "campos enriquecidos, entidades añadidas y gaps cerrados."
        ),
        "state": "persistent gap attempts, source health, cache and discovery queue",
        "public_runtime": "lazy-loaded data/public section projection",
    }

    normalize_fields(data)
    apply_curated_distributors(data)
    apply_curated(data)
    normalize_fields(data)

    # First graph pass recovers the canonical relation seed and newly researched atomic items.
    graph = build_graph(data)
    project_graph_to_views(data, graph)
    normalize_fields(data)
    derive_overlap_fields(data)
    derive_secondary_views(data)
    _sync_source_catalog(data)

    # The second pass makes the graph and every projected comparison view converge.
    graph = build_graph(data)
    project_graph_to_views(data, graph)
    derive_overlap_fields(data)
    # Client Intelligence is additive and cannot erase canonical knowledge.
    derive_client_intelligence(data)
    # Knowledge Guard: a research/build pass may enrich or update, but never silently
    # delete stable Trends, Architectures or non-relational manufacturer knowledge.
    restore_protected_knowledge(data, knowledge_baseline)
    apply_westcon_document_provenance(data)
    mark_legacy_unresolved(data)
    sync_document_sources(data)
    normalize_fields(data)
    _sync_source_catalog(data)
    gaps = build_gaps(data, VERSION, research_state)
    metrics = calculate(data, gaps, graph)

    baseline = read_json("config/current/release_baseline_metrics.json")
    before = baseline["before"]
    delta_keys = (
        "entities_total", "sources", "domains_unique", "evidences",
        "official_evidences", "traceable_fields", "gaps_total", "gaps_critical",
        "relations", "manufacturer_distributor_confirmed",
        "manufacturer_integrator_confirmed", "client_technology_relations",
    )
    delta = {key: metrics.get(key, 0) - before.get(key, 0) for key in delta_keys}
    compare = {
        "definition": (
            f"{baseline.get('version', 'baseline')} → {VERSION}; misma definición estricta de gap, "
            "con trazabilidad atómica y memoria persistente de investigación."
        ),
        "before": before,
        "after": metrics,
        "delta": delta,
        "gap_reduction_pct": round(
            (before.get("gaps_total", 0) - metrics["gaps_total"]) * 100 / max(1, before.get("gaps_total", 0)),
            2,
        ),
    }

    quality = audit(data, graph, gaps)
    if quality["errors"]:
        raise ValueError("Quality gate failed: " + "; ".join(quality["errors"][:5]))
    meta["source_count"] = metrics["sources"]
    meta["quality_score"] = quality["score"]

    last_run = {
        "version": VERSION,
        "generated_at": now,
        "finished_at": now,
        "profile": ledger.get("profile") or "release-build",
        "status": "published",
        "sources": metrics["sources"],
        "traceable_fields": metrics["traceable_fields"],
        "research_gaps": metrics["gaps_total"],
        "critical_gaps": metrics["gaps_critical"],
        "manufacturers": metrics["manufacturers"],
        "distributors": metrics["distributors"],
        "integrators": metrics["integrators"],
        "clients": metrics["clients_public"] + metrics["clients_private"],
        "trends": metrics["trends"],
        "architectures": metrics["architectures"],
        "research_quality": {
            "fetch_attempts": ledger.get("fetch_attempts", 0),
            "fetch_successes": ledger.get("fetch_successes", 0),
            "pages_relevant": ledger.get("pages_relevant", 0),
            "accepted_evidences": ledger.get("accepted_evidences", 0),
            "fields_enriched": ledger.get("fields_enriched", 0),
            "values_added": ledger.get("values_added", 0),
            "entities_added": ledger.get("entities_added", 0),
            "circuit_skips": ledger.get("circuit_skips", 0),
        },
        "quality_score": quality["score"],
        "provenance": provenance_summary(data),
    }

    internal_data = json_bytes(data, pretty=False)
    public_files, manifest = public_payloads(data, last_run)
    compare["public_projection"] = {
        "manifest_bytes": len(public_files["data/public/manifest.json"]),
        "sections_bytes": sum(
            metadata["bytes"] for metadata in manifest["sections"].values()
        ),
        "internal_intelligence_bytes": len(internal_data),
    }

    files = {
        "data/current/intelligence.json": internal_data,
        "data/current/research_state.json": json_bytes(research_state),
        "data/current/relationship_graph.json": json_bytes(graph),
        "data/current/research_gaps.json": json_bytes(gaps),
        "data/current/metrics_before_after.json": json_bytes(compare),
        "data/current/coverage_report.json": json_bytes(gaps["coverage"]),
        "data/current/source_report.json": json_bytes({
            "version": VERSION,
            "sources": len(data.get("source_catalog") or []),
            "domains_unique": metrics["domains_unique"],
            "official_evidences": metrics["official_evidences"],
            "traceable_fields": metrics["traceable_fields"],
            "provenance": provenance_summary(data),
        }),
        "data/current/quality_report.json": json_bytes(quality),
        "data/current/last_run.json": json_bytes(last_run),
    }
    files.update(public_files)
    atomic_write_many(files)
    return compare


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
