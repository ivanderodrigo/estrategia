"""Canonical build pipeline with transactional publication."""

from __future__ import annotations

import json
from copy import deepcopy
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
from .gaps import build_gaps, validate_gap_state_contract
from .archive_provenance import (
    apply_archive_provenance,
    archive_registry_summary,
    load_archive_registry,
)
from .client_intelligence import derive_client_intelligence
from .business_schema import apply_business_schema
from .confidence import apply_confidence_model
from .knowledge_provenance import (
    apply_westcon_document_provenance,
    apply_public_evidence_migrations,
    convert_internal_lineage_to_research_seeds,
    seed_from_knowledge_baseline,
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
from .preservation import (
    audit as audit_preservation,
    dedupe_manufacturer_lists,
    restore_accredited_support,
    restore_preserved_relations,
    restore_research_seed_support,
    sync_research_seed_registry,
    snapshot as preservation_snapshot,
)
from .source_rationalization import rationalize_sources
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
    existing_graph = read_json("data/current/relationship_graph.json", {})
    # Preserve the exact post-research input as the reconciliation source. Canonical build
    # steps may normalize ids/fields, but must not detach valid support from surviving facts.
    preservation_source = deepcopy(data)
    knowledge_baseline = load_knowledge_baseline()
    # HF7: internal/PPT lineage is research memory, never accrediting support. Convert and
    # seed the snapshot copy first so the Preservation Gate protects clues without treating them as proof.
    seed_snapshot_stats = convert_internal_lineage_to_research_seeds(preservation_source)
    baseline_seed_snapshot_stats = seed_from_knowledge_baseline(preservation_source, knowledge_baseline)
    seed_registry_snapshot = sync_research_seed_registry(preservation_source)
    preservation_before = preservation_snapshot(preservation_source, existing_graph)
    archive_registry = load_archive_registry()
    restore_protected_knowledge(data, knowledge_baseline)
    apply_westcon_document_provenance(data)
    archive_apply_start = apply_archive_provenance(data, archive_registry)
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
            "validate", "source-rationalize", "historical-revalidate", "item-provenance", "graph", "gap", "learn", "publish",
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
    schema_stats = apply_business_schema(data)

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
    archive_apply_final = apply_archive_provenance(data, archive_registry)
    mark_legacy_unresolved(data)
    sync_document_sources(data)
    normalize_fields(data)
    # Bind documentary lineage to final normalized items, then immediately demote it to
    # non-accrediting research memory. Public web evidence is the only external accreditation.
    document_apply_final = apply_westcon_document_provenance(data)
    internal_seed_migration = convert_internal_lineage_to_research_seeds(data)
    baseline_seed_migration = seed_from_knowledge_baseline(data, knowledge_baseline)
    public_evidence_migration = apply_public_evidence_migrations(
        data, read_json("config/current/public_evidence_migrations.json", {})
    )

    # HF4 reconciliation: canonicalization is allowed to reshape representation, never to
    # detach accredited evidence from a knowledge item that still exists. Reattach the exact
    # pre-build support first, then preserve graph relations across deterministic id re-keying.
    support_reconciliation = restore_accredited_support(data, preservation_source)
    relation_reconciliation = restore_preserved_relations(graph, existing_graph, data)
    # Re-project relation-owned comparison views after graph reconciliation. These fields are
    # build-owned and explicitly excluded from immutable-fact preservation.
    project_graph_to_views(data, graph)
    derive_overlap_fields(data)
    manufacturer_deduplication = dedupe_manufacturer_lists(data)
    # HF8: reattach non-accrediting clues to surviving exact claims where possible, then
    # persist every clue in an internal registry that is independent from table projection.
    research_seed_reconciliation = restore_research_seed_support(data, preservation_source)
    research_seed_registry = sync_research_seed_registry(data, preservation_source)
    # Re-run the public bootstrap after dedup so claim-specific public support stays attached
    # to the final atomic item. Internal lineage remains present only as a research seed.
    public_evidence_migration_final = apply_public_evidence_migrations(
        data, read_json("config/current/public_evidence_migrations.json", {})
    )
    _sync_source_catalog(data)
    confidence_stats = apply_confidence_model(data)
    source_rationalization = rationalize_sources(data)
    gaps = build_gaps(data, VERSION, research_state)
    metrics = calculate(data, gaps, graph)
    metrics.update({
        "evidence_support_pending": int(gaps.get("evidence_support_gaps") or 0),
        "derivation_support_pending": int(gaps.get("derivation_support_gaps") or 0),
        "historical_revalidation_pending": int(gaps.get("historical_revalidation_gaps") or 0),
        "claims_publicly_accredited": int(source_rationalization.get("targets_supported_public_only") or 0),
        "claims_westcon_supported": 0,
        "claims_westcon_and_public": 0,
        "claims_pending": int(source_rationalization.get("support_pending_unique_claims") or 0),
        "public_validation_pending": int(gaps.get("public_validation_gaps") or 0),
        "unknown_research_gaps": int(gaps.get("unknown_research_gaps") or 0),
    })

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

    preservation_after = preservation_snapshot(data, graph)
    preservation = audit_preservation(
        preservation_before,
        preservation_after,
        read_json("config/current/preservation_exceptions.json", {}),
    )
    preservation["reconciliation"] = {
        "accredited_support": support_reconciliation,
        "relations": relation_reconciliation,
        "manufacturer_deduplication": manufacturer_deduplication,
        "internal_seed_snapshot": seed_snapshot_stats,
        "baseline_seed_snapshot": baseline_seed_snapshot_stats,
        "seed_registry_snapshot": seed_registry_snapshot,
        "internal_seed_migration": internal_seed_migration,
        "baseline_seed_migration": baseline_seed_migration,
        "research_seed_reconciliation": research_seed_reconciliation,
        "research_seed_registry": research_seed_registry,
        "public_evidence_migration": public_evidence_migration,
        "public_evidence_migration_final": public_evidence_migration_final,
    }
    # The legacy quality module only knows one open-state label ("Por investigar"). HF8
    # validates the richer state contract itself, then feeds a label-compatible copy to that
    # legacy invariant. The persisted gap report keeps the real differentiated states.
    gap_state_errors = validate_gap_state_contract(gaps)
    legacy_quality_gaps = deepcopy(gaps)
    for gap in legacy_quality_gaps.get("gaps") or []:
        if isinstance(gap, dict) and gap.get("research_state") == "Pendiente de validación pública":
            gap["research_state"] = "Por investigar"
    quality = audit(data, graph, legacy_quality_gaps)
    if gap_state_errors:
        quality["errors"].extend("HF8 gap-state contract: " + error for error in gap_state_errors)
    if preservation["errors"]:
        quality["errors"].extend("Preservation gate: " + error for error in preservation["errors"])
        quality["score"] = max(0, 100 - len(quality["errors"]) * 8 - min(20, len(quality.get("warnings") or [])))
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
        "archive_provenance": archive_registry_summary(archive_registry),
        "archive_apply": archive_apply_final,
        "document_apply": document_apply_final,
        "schema": schema_stats,
        "confidence_model": confidence_stats,
        "knowledge_preservation": preservation,
        "source_intelligence": {
            "historical_total": source_rationalization.get("historical_total", 0),
            "historical_supported_current_open": source_rationalization.get("historical_supported_current_open", 0),
            "historical_search_required": source_rationalization.get("historical_search_required", 0),
            "historical_supported_westcon": source_rationalization.get("historical_supported_westcon", 0),
            "historical_supported_public": source_rationalization.get("historical_supported_public", 0),
            "historical_supported_westcon_and_public": source_rationalization.get("historical_supported_westcon_and_public", 0),
            "targets_supported": source_rationalization.get("targets_supported", 0),
            "targets_search_required": source_rationalization.get("targets_search_required", 0),
            "claims_publicly_accredited": metrics["claims_publicly_accredited"],
            "claims_westcon_supported": metrics["claims_westcon_supported"],
            "claims_westcon_and_public": metrics["claims_westcon_and_public"],
            "claims_pending": metrics["claims_pending"],
        },
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
            "archive_provenance": archive_registry_summary(archive_registry),
            "source_intelligence": source_rationalization,
        }),
        "data/current/provenance_report.json": json_bytes({
            "version": VERSION,
            "summary": provenance_summary(data),
            "archive_registry": archive_registry_summary(archive_registry),
            "archive_apply": archive_apply_final,
            "document_apply": document_apply_final,
            "source_intelligence": source_rationalization,
        }),
        "data/current/source_rationalization.json": json_bytes(source_rationalization),
        "data/current/knowledge_preservation_v410.json": json_bytes(preservation),
        "data/current/quality_report.json": json_bytes(quality),
        "data/current/last_run.json": json_bytes(last_run),
    }
    files.update(public_files)
    atomic_write_many(files)
    return compare


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
