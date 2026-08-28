from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v34.common import load_json, write_json
from v34.ecosystem_motion import build_ecosystem_motion
from v34.entity_intelligence import build_entities
from v34.intelligence_outputs import build_adaptive_queue, build_history, build_source_catalog, build_source_coverage
from v34.relationship_engine import build_relationships
from v39.build_intelligence import build as build_public_intelligence

OBSOLETE_DECISION_OUTPUTS = (
    "recommendations.json",
    "recommendation_audit.json",
    "business_intelligence_report.json",
    "quality_report.json",
    "metrics_before_after.json",
    "last_run.json",
)


def _merged_source_expansion(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_expansion = load_json(root / "config/v34/source_expansion.json", {})
    audience_routes = load_json(root / "config/v34/audience_source_routes.json", {})
    relationship_playbook = load_json(root / "config/v34/relationship_source_playbook.json", {})
    additions = [
        load_json(root / "config/v35/source_additions.json", {}),
        load_json(root / "config/v36/source_additions.json", {}),
        load_json(root / "config/v38/source_additions.json", {}),
        load_json(root / "config/v39/source_additions.json", {}),
    ]
    merged_sources: dict[str, dict[str, Any]] = {}
    for source in [*(source_expansion.get("sources") or []), *(audience_routes.get("sources") or []), *[item for block in additions for item in (block.get("sources") or [])]]:
        source_id = source.get("id") or source.get("source_id")
        if source_id:
            merged_sources[str(source_id)] = {**source, "id": source_id}
    merged = {
        **source_expansion,
        "sources": list(merged_sources.values()),
        "audience_routes": audience_routes.get("routes") or [],
        "audience_rules": audience_routes.get("rules") or [],
    }
    return merged, audience_routes, relationship_playbook


def _remove_obsolete_decision_outputs(root: Path) -> list[str]:
    removed: list[str] = []
    directory = root / "data/v34"
    for name in OBSOLETE_DECISION_OUTPUTS:
        path = directory / name
        if path.exists():
            path.unlink()
            removed.append(name)
    return removed


def run(root: Path, profile: str = "daily", foundation_rc: int = 0) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    source_expansion, audience_routes, relationship_playbook = _merged_source_expansion(root)
    entities, identity_audit = build_entities(root)
    relationships = build_relationships(root, entities)
    ecosystem_motion = build_ecosystem_motion(root, entities, relationships, audience_routes, relationship_playbook)
    source_coverage = build_source_coverage(root, entities, source_expansion)
    source_catalog = build_source_catalog(source_expansion)
    history = build_history(root)
    research_queue = build_adaptive_queue(entities, relationships, source_coverage)

    out34 = root / "data/v34"
    out34.mkdir(parents=True, exist_ok=True)
    write_json(out34 / "entities.json", entities)
    write_json(out34 / "identity_audit.json", identity_audit)
    write_json(out34 / "relationships.json", relationships)
    write_json(out34 / "ecosystem_motion_intelligence.json", ecosystem_motion)
    write_json(out34 / "source_coverage.json", source_coverage)
    write_json(out34 / "source_catalog.json", source_catalog)
    write_json(out34 / "historical_intelligence.json", history)
    legacy_arch = out34 / "architectures.json"
    if legacy_arch.exists():
        legacy_arch.unlink()
    write_json(out34 / "research_queue.json", research_queue)
    removed = _remove_obsolete_decision_outputs(root)

    public = build_public_intelligence()
    out39 = root / "data/v39"
    out39.mkdir(parents=True, exist_ok=True)
    write_json(out39 / "intelligence.json", public)
    legacy_gaps = load_json(root / "data/v38/research_gaps.json", {}) or {}
    write_json(out39 / "research_gaps.json", {
        **legacy_gaps,
        "version": "3.9.0",
        "note": "La cola interna v3.9.0 hereda y reusa la investigación base v3.8 mientras amplía la cobertura a clientes públicos y privados.",
    })

    finished = datetime.now(timezone.utc)
    result = {
        "version": "3.9.0",
        "profile": profile,
        "status": "published",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "runtime_seconds": round((finished - started).total_seconds(), 3),
        "foundation_rc": foundation_rc,
        "manufacturers": len(public.get("manufacturers", [])),
        "distributors": len(public.get("distributors", [])),
        "integrators": len(public.get("integrators", [])),
        "clients": len(public.get("clients_public", [])) + len(public.get("clients_private", [])),
        "clients_public": len(public.get("clients_public", [])),
        "clients_private": len(public.get("clients_private", [])),
        "trends": len(public.get("trends", [])),
        "architectures": len(public.get("architectures", [])),
        "source_count": len(public.get("source_catalog", [])),
        "research_gaps": legacy_gaps.get("total_gaps", 0),
        "high_priority_research_gaps": legacy_gaps.get("high_priority_gaps", 0),
        "traceable_fields": sum(
            1
            for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures")
            for row in public.get(section, [])
            for value in (row.get("fields") or {}).values()
            if value and value.get("evidence")
        ),
        "obsolete_decision_outputs_removed": removed,
    }
    write_json(out39 / "last_run.json", result)
    return result
