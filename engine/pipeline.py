from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .enrichment import apply_curated, apply_curated_distributors, derive_overlap_fields, derive_secondary_views, normalize_fields, project_graph_to_views
from .gaps import build_gaps
from .graph import build_graph
from .metrics import calculate
from .publication import build_public
from .quality import audit

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.20.0"


def load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write(rel: str, obj: Any, pretty: bool = True) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")),
        encoding="utf-8",
    )


def _sync_source_catalog(data: dict[str, Any]) -> None:
    catalog = list(data.get("source_catalog") or [])
    seen = {str(x.get("url") or "") for x in catalog if isinstance(x, dict) and x.get("url")}
    for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures"):
        for row in data.get(section) or []:
            for field in (row.get("fields") or {}).values():
                rows = list(field.get("evidence") or [])
                for item in field.get("items") or []:
                    if isinstance(item, dict):
                        rows.extend(item.get("evidence") or [])
                for ev in rows:
                    if not isinstance(ev, dict):
                        continue
                    url = str(ev.get("url") or "")
                    if not url.startswith("http") or url in seen:
                        continue
                    seen.add(url)
                    catalog.append({
                        "name": ev.get("source") or ev.get("title") or "Fuente pública",
                        "class": ev.get("source_type") or "public-web",
                        "scope": [ev.get("scope") or "GLOBAL"],
                        "dimensions": [section],
                        "url": url,
                    })
    data["source_catalog"] = catalog


def run() -> dict[str, Any]:
    data = load("data/current/intelligence.json")
    now = datetime.now(timezone.utc).isoformat()
    data.setdefault("meta", {})["version"] = VERSION
    data["meta"]["generated_at"] = now
    data["meta"]["principle"] = "Hipersofisticada por dentro. Extremadamente sencilla por fuera."
    data["meta"]["research_engine"] = {
        "version": VERSION,
        "pipeline": ["plan", "fetch", "relevance", "extract", "candidate", "validate", "apply", "graph", "corroborate", "gap", "learn"],
        "success_definition": "La descarga correcta no equivale a inteligencia: se mide evidencia aceptada, campos enriquecidos y gaps cerrados.",
        "public_runtime": "data/public section projection",
    }

    # 1) Add new official evidence and normalize derivative views.
    normalize_fields(data)
    apply_curated_distributors(data)
    apply_curated(data)
    normalize_fields(data)
    derive_overlap_fields(data)

    # 2) Build canonical graph, then project the graph back into comparison views.
    graph = build_graph(data)
    project_graph_to_views(data, graph)
    normalize_fields(data)
    derive_secondary_views(data)
    _sync_source_catalog(data)

    # 3) Recompute graph once after curated vendor relations; then strict gaps and metrics.
    graph = build_graph(data)
    gaps = build_gaps(data, VERSION)
    metrics = calculate(data, gaps, graph)

    baseline = load("config/current/release_baseline_metrics.json")
    before = baseline["before"]
    delta_keys = [
        "entities_total", "sources", "domains_unique", "evidences", "official_evidences", "traceable_fields",
        "gaps_total", "relations", "manufacturer_distributor_confirmed", "manufacturer_integrator_confirmed", "client_technology_relations",
    ]
    delta = {k: metrics.get(k, 0) - before.get(k, 0) for k in delta_keys}
    compare = {
        "definition": "v3.19.0 → v3.20.0 con definición estricta: un valor no cierra un gap sin evidencia pública suficiente; las señales se mantienen separadas de los hechos.",
        "before": before,
        "after": metrics,
        "delta": delta,
        "gap_reduction_pct": round((before["gaps_total"] - metrics["gaps_total"]) * 100 / max(1, before["gaps_total"]), 2),
    }

    quality = audit(data, graph, gaps)
    data["meta"]["source_count"] = metrics["sources"]
    data["meta"]["quality_score"] = quality["score"]

    # 4) Persist internal truth. These files are not published by Pages.
    write("data/current/intelligence.json", data, False)
    write("data/current/relationship_graph.json", graph)
    write("data/current/research_gaps.json", gaps)
    write("data/current/metrics_before_after.json", compare)
    write("data/current/coverage_report.json", gaps["coverage"])
    write("data/current/source_report.json", {
        "version": VERSION,
        "sources": len(data.get("source_catalog", [])),
        "domains_unique": metrics["domains_unique"],
        "official_evidences": metrics["official_evidences"],
        "traceable_fields": metrics["traceable_fields"],
    })
    write("data/current/quality_report.json", quality)

    ledger = {}
    try:
        ledger = load("data/current/research_ledger.json")
    except Exception:
        pass
    last_run = {
        "version": VERSION,
        "generated_at": now,
        "finished_at": now,
        "profile": "release-build",
        "status": "published",
        "sources": metrics["sources"],
        "traceable_fields": metrics["traceable_fields"],
        "research_gaps": metrics["gaps_total"],
        "manufacturers": metrics["manufacturers"],
        "distributors": metrics["distributors"],
        "integrators": metrics["integrators"],
        "clients": metrics["clients_public"] + metrics["clients_private"],
        "trends": len(data.get("trends") or []),
        "architectures": len(data.get("architectures") or []),
        "research_quality": {
            "fetch_attempts": ledger.get("fetch_attempts", 0),
            "fetch_successes": ledger.get("fetch_successes", 0),
            "pages_relevant": ledger.get("pages_relevant", 0),
            "accepted_evidences": ledger.get("accepted_evidences", 0),
            "fields_enriched": ledger.get("fields_enriched", 0),
            "values_added": ledger.get("values_added", 0),
        },
        "quality_score": quality["score"],
    }
    write("data/current/last_run.json", last_run)

    # 5) Generate a deliberately smaller public projection with section-level lazy loading.
    manifest = build_public(data, last_run)
    compare["public_projection"] = {
        "manifest_bytes": (ROOT / "data/public/manifest.json").stat().st_size,
        "sections_bytes": sum(x["bytes"] for x in manifest["sections"].values()),
        "internal_intelligence_bytes": (ROOT / "data/current/intelligence.json").stat().st_size,
    }
    write("data/current/metrics_before_after.json", compare)
    return compare


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
