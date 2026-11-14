"""Curated *public* research verified against exact primary source pages.

Unlike a generic discovery search, each claim in the registry has its own link.
The topic rules match only the row title, never arbitrary prose, and attach no
source to an unrelated field or vendor/channel relation.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .enrichment import merge_field
from .model import canonical
from .storage import read_json


def _claim_field(field_id: str, claims: list[list[Any]]) -> dict[str, Any]:
    items = []
    for pair in claims:
        value, source = pair
        if not isinstance(value, str) or not isinstance(source, dict):
            continue
        ev = deepcopy(source)
        ev["field"] = field_id
        ev["item_value"] = value
        ev["atomic"] = True
        ev["source_binding"] = "claim-specific"
        items.append({"value": value, "evidence": [ev],
                      "confidence": 0.86, "claim_type": "fact",
                      "assertion_status": "CONFIRMADO"})
    return {"value": [x["value"] for x in items], "items": items,
            "evidence": [], "confidence": 0.86, "claim_type": "fact",
            "assertion_status": "CONFIRMADO"}


def _safe_research_merge(current: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Never replace an accredited scalar with a different claim.
    
    The same category can be described by multiple sources, but only list-valued
    fields are additive. A scalar text is immutable unless it is empty.
    """
    old_value = current.get("value")
    new_value = new.get("value")
    if old_value not in (None, "", [], {}) and not isinstance(old_value, list):
        candidates = new_value if isinstance(new_value, list) else [new_value]
        if not any(canonical(old_value) == canonical(value) for value in candidates):
            return current
        return merge_field(current, {**new, "value": old_value})
    return merge_field(current, new)


def apply_verified_research(data: dict[str, Any]) -> dict[str, int]:
    registry = read_json("config/current/verified_research_20261113.json", {})
    stats = {"manufacturer_values_added": 0, "trend_values_added": 0,
             "architecture_values_added": 0, "rows_enriched": 0,
             "existing_claims_accredited": 0}
    if not isinstance(registry, dict):
        return stats
    by_section = registry.get("entities") or {}
    for section, names in by_section.items():
        if section != "manufacturers":
            continue
        for row in data.get(section) or []:
            specs = names.get(row.get("name")) or {}
            if not specs:
                continue
            fields = row.setdefault("fields", {})
            touched = False
            for field_id, claims in specs.items():
                existing = fields.get(field_id) or {}
                old = {canonical(x) for x in (
                    existing.get("value") if isinstance(existing.get("value"), list)
                    else ([existing.get("value")] if existing.get("value") else [])
                )}
                facts = _claim_field(field_id, claims)
                fields[field_id] = _safe_research_merge(existing, facts)
                result_value = fields[field_id].get("value")
                actual = result_value if isinstance(result_value, list) else ([result_value] if result_value else [])
                newly = sum(1 for value in actual if canonical(value) not in old)
                stats["manufacturer_values_added"] += newly
                touched |= bool(newly)
            stats["rows_enriched"] += int(touched)

    # Topic evidence is attached to one *exact* field and claim; a report about
    # Zero Trust cannot substantiate an unrelated revenue, market-share or linecard.
    for section, counter in (("trends", "trend_values_added"),
                             ("architectures", "architecture_values_added")):
        rules = [rule for rule in registry.get("topic_rules") or []
                 if rule.get("section") == section]
        for row in data.get(section) or []:
            name = str(row.get("name") or "")
            fields = row.setdefault("fields", {})
            touched = False
            for rule in rules:
                pattern = str(rule.get("pattern") or "")
                if not pattern or not re.search(pattern, name, re.IGNORECASE):
                    continue
                field_id = str(rule.get("field") or "")
                if field_id not in (("sources", "drivers", "observed") if section == "trends"
                                    else ("analyst_basis", "principles", "context")):
                    continue
                claims = rule.get("values") or []
                old_field = fields.get(field_id) or {}
                old = {canonical(x) for x in (
                    old_field.get("value") if isinstance(old_field.get("value"), list)
                    else ([old_field.get("value")] if old_field.get("value") else [])
                )}
                fields[field_id] = _safe_research_merge(old_field, _claim_field(field_id, claims))
                result_value = fields[field_id].get("value")
                actual = result_value if isinstance(result_value, list) else ([result_value] if result_value else [])
                added = sum(1 for value in actual if canonical(value) not in old)
                stats[counter] += added
                touched |= bool(added)
            stats["rows_enriched"] += int(touched)
    # Backfill the source for an ALREADY present, exact vendor assertion.
    # This is not category similarity, a discovered partner or a generated
    # competitor. The official page must name the product/vendor's role.
    # Do not fabricate new layer memberships or missing market participants.
    structured = read_json("config/current/historical_structured_verified.json", {})
    exact_sources = list(registry.get("existing_claim_sources") or [])
    exact_sources.extend(structured.get("existing_claim_sources") or [])
    historical_market = read_json("config/current/verified_historical_market_20261114.json", {})
    exact_sources.extend(historical_market.get("existing_claim_sources") or [])
    historical_peers = read_json("config/current/verified_historical_peer_20261114.json", {})
    exact_sources.extend(historical_peers.get("existing_claim_sources") or [])
    issuer_competitors = read_json("config/current/verified_issuer_competitors_20261114.json", {})
    exact_sources.extend(issuer_competitors.get("existing_claim_sources") or [])
    topic_market = read_json("config/current/verified_historical_topic_markets_20261114.json", {})
    exact_sources.extend(topic_market.get("existing_claim_sources") or [])
    semantic_history = read_json("config/current/historical_semantic_verified.json", {})
    exact_sources.extend(semantic_history.get("existing_claim_sources") or [])
    for claim in exact_sources:
        section = str(claim.get("section") or "")
        field_id = str(claim.get("field") or "")
        # The semantic registry is a separately reviewed, exact historical
        # URL/excerpt assertion. All other registries retain their narrow scope.
        semantic_fields = {
            "manufacturers": {"capabilities"},
            "distributors": {"services", "capabilities", "specializations", "technology_domains",
                             "training", "marketplace", "logistics", "financing", "verticals",
                             "vendor_relations", "linecard_remainder"},
            "integrators": {"vendor_relations", "manufacturer_relations", "vendor_partnerships",
                            "partnerships", "capabilities", "specializations", "services",
                            "technology_domains", "technology_specializations", "service_portfolio",
                            "alliances"},
            "clients_private": {"technology_signals", "hiring_signals"},
            "trends": {"sources"},
            "architectures": {"analyst_basis"},
        }
        source = claim.get("source") or {}
        exact_semantic = (
            isinstance(source, dict)
            and source.get("source_type") == "historical-verified-excerpt"
            and str(source.get("verification_method") or "").startswith("VERIFIED_")
            and field_id in semantic_fields.get(section, set())
            and str(source.get("description") or "").startswith("Extracto de evidencia:")
        )
        if not exact_semantic and (section, field_id) not in {
            ("manufacturers", "competitors"),
            ("architectures", "vendors"),
            ("architectures", "context"),
            ("architectures", "principles"),
            ("trends", "market_players"),
        }:
            continue
        entity = str(claim.get("entity") or "")
        value = str(claim.get("value") or "")
        source = claim.get("source") or {}
        if not entity or not value or not isinstance(source, dict):
            continue
        for row in data.get(section) or []:
            if canonical(row.get("name")) != canonical(entity):
                continue
            field = (row.get("fields") or {}).get(field_id) or {}
            old_values = field.get("value") if isinstance(field.get("value"), list) else ([field.get("value")] if field.get("value") not in (None, "", []) else [])
            match = next((v for v in old_values if canonical(v) == canonical(value)), None)
            if match is None:
                # A manually audited product-alternative citation may recover a
                # missing historical competitor value. All other relationship
                # fields still require an existing exact assertion.
                url = str(source.get("url") or "")
                exact_historical = (
                    section == "manufacturers" and field_id == "competitors"
                    and (
                        (source.get("source_type") == "analyst-peer-review"
                         and url.startswith("https://www.gartner.com/reviews/product/")
                         and url.rstrip("/").endswith("/alternatives"))
                        or (source.get("source_type") == "analyst-market-comparison"
                            and source.get("verification_method") == "same-market-explicit-vendor-list"
                            and url.startswith("https://www.gartner.com/en/documents/"))
                        or (source.get("source_type") == "official-regulatory-filing"
                            and source.get("verification_method") == "issuer-identified-direct-competitor"
                            and (
                                (canonical(entity) == "audiocodes"
                                 and url.startswith("https://www.otcmarkets.com/filing/html"))
                                or (canonical(entity) == "ciena"
                                    and canonical(source.get("issuer")) == "ciena"
                                    and url == "https://www.sec.gov/Archives/edgar/data/936395/000162828025056698/cien-20251101.htm")
                            ))
                    )
                )
                if not exact_historical:
                    continue
                match = value
            # Preserve the exact published spelling and all existing support.
            new = _claim_field(field_id, [[match, source]])
            if not isinstance(field.get("value"), list):
                # Scalar architecture assertions have field-level, not item-level,
                # provenance. Keep the original scalar and attach the exact proof.
                new = {**new, "value": match,
                       "evidence": list(new["items"][0]["evidence"])}
            row["fields"][field_id] = merge_field(field, new)
            stats["existing_claims_accredited"] += 1
            break
    return stats
