from __future__ import annotations

from urllib.parse import urlparse

from .settings import SECTIONS
from .knowledge_provenance import provenance_kind, typed_evidence_sufficient


def calculate(data, gaps, graph):
    evidence_keys = set(); official_keys = set(); source_urls = set(); domains = set(); traceable = 0; populated = 0
    for section in SECTIONS:
        for row in data.get(section, []):
            for field in (row.get("fields") or {}).values():
                value = field.get("value")
                if value not in (None, "", [], {}):
                    populated += 1
                rows = list(field.get("evidence") or [])
                for item in field.get("items") or []:
                    if isinstance(item, dict):
                        rows.extend(item.get("evidence") or [])
                valid = 0
                for ev in rows:
                    if not isinstance(ev, dict):
                        continue
                    url = str(ev.get("url") or "")
                    key = (url, str(ev.get("title") or ""), str(ev.get("source") or ""), str(ev.get("date") or ""))
                    if any(key) and provenance_kind(ev) != "LEGACY_UNRESOLVED":
                        evidence_keys.add(key)
                    if typed_evidence_sufficient(ev):
                        valid += 1
                        if ev.get("official") is True or str(ev.get("source_grade") or "").startswith("A"):
                            official_keys.add(key)
                    if url.startswith(("http://", "https://")):
                        source_urls.add(url)
                    host = urlparse(url).netloc.lower().removeprefix("www.")
                    if host:
                        domains.add(host)
                traceable += int(valid > 0 and value not in (None, "", [], {}))
    for src in data.get("source_catalog", []):
        url = str(src.get("url") or "") if isinstance(src, dict) else ""
        if url.startswith(("http://", "https://")):
            source_urls.add(url)
            host = urlparse(url).netloc.lower().removeprefix("www.")
            if host: domains.add(host)
    return {
        "entities_total": sum(len(data.get(s, [])) for s in SECTIONS),
        "manufacturers": len(data.get("manufacturers", [])),
        "distributors": len(data.get("distributors", [])),
        "integrators": len(data.get("integrators", [])),
        "clients_public": len(data.get("clients_public", [])),
        "clients_private": len(data.get("clients_private", [])),
        "trends": len(data.get("trends", [])),
        "architectures": len(data.get("architectures", [])),
        "sources": len(source_urls),
        "domains_unique": len(domains),
        "evidences": len(evidence_keys),
        "official_evidences": len(official_keys),
        "fields_populated": populated,
        "traceable_fields": traceable,
        "gaps_total": gaps["total_gaps"],
        "gaps_critical": gaps["critical_gaps"],
        "gaps_by_section": gaps["by_section"],
        "relations": len(graph["relationships"]),
        "manufacturer_distributor_confirmed": sum(1 for r in graph["relationships"] if r["relation"] == "distributes" and r["status"] == "CONFIRMADO"),
        "manufacturer_integrator_confirmed": sum(1 for r in graph["relationships"] if r["relation"] == "partners_with" and r["status"] == "CONFIRMADO"),
        "client_technology_relations": sum(1 for r in graph["relationships"] if r["relation"] == "technology_signal"),
    }
