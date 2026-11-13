"""Compact, evidence-preserving triage of hard-to-verify observatory claims.

Designed to run inside GitHub Actions, where the full (large) canonical dataset
is available. No gap is closed, no URL is accepted without a fresh source fetch.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

HIGH_YIELD = {
    "distributors": {"vendor_relations", "services", "capabilities",
                     "specializations", "technology_domains", "logistics",
                     "marketplace", "training", "financing", "local_presence"},
    "integrators": {"services", "capabilities", "technology_domains",
                    "specializations", "verticals", "vendor_relations",
                    "managed_services", "msp_mssp", "public_cases"},
    "manufacturers": {"products_platforms", "capabilities", "services",
                       "use_cases", "partner_program", "certifications"},
    "clients_public": {"cpv_codes", "estimated_amount", "identified_vendors"},
    "clients_private": {"technology_signals", "technology_domains"},
    "trends": set(),
    "architectures": set(),
}


def summarize(report: dict, intelligence: dict | None = None) -> dict:
    by_field = defaultdict(lambda: {"claims": 0, "values": 0, "entities": set(),
                                    "explicit_leads": 0, "official_leads": 0,
                                    "sample": []})
    by_entity = defaultdict(lambda: {"fields": set(), "claims": 0,
                                     "values": 0, "lead_urls": set()})
    classes = Counter()
    for gap in report.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        section = str(gap.get("section") or "")
        entity = str(gap.get("entity") or "")
        field = str(gap.get("field") or "")
        kind = str(gap.get("gap_kind") or "")
        values = [v for v in gap.get("target_values") or []
                  if isinstance(v, str) and v.strip()]
        if kind == "derivation-support":
            classes["derive"] += 1
            continue
        if not values:
            classes["missing_or_unspecified"] += 1
            continue
        classes["assertion"] += 1
        name = f"{section}.{field}"
        row = by_field[name]
        row["claims"] += 1
        row["values"] += len(values)
        row["entities"].add(entity)
        leads = [url for lead in gap.get("revalidation_seeds") or []
                 if isinstance(lead, dict)
                 for url in [str(lead.get("url") or "")]
                 if url.startswith("https://")]
        row["explicit_leads"] += int(bool(leads))
        row["official_leads"] += int(any(lead.get("official")
            for lead in gap.get("revalidation_seeds") or [] if isinstance(lead, dict)))
        key = (section, entity)
        by_entity[key]["fields"].add(field)
        by_entity[key]["claims"] += 1
        by_entity[key]["values"] += len(values)
        by_entity[key]["lead_urls"].update(leads[:4])
        if len(row["sample"]) < 3:
            row["sample"].append({
                "entity": entity, "values": values[:4], "source_leads": leads[:2],
                "kind": kind,
            })

    rows = []
    for key, value in by_field.items():
        section, field = key.split(".", 1)
        rows.append({
            "field": key, "claims": value["claims"], "values": value["values"],
            "entities": len(value["entities"]),
            "high_yield": field in HIGH_YIELD.get(section, set()),
            "with_direct_leads": value["explicit_leads"],
            "with_official_leads": value["official_leads"],
            "sample": value["sample"],
        })
    rows.sort(key=lambda r: (
        not r["high_yield"], -r["claims"], r["field"],
    ))
    high_yield_claims = sum(r["claims"] for r in rows if r["high_yield"])
    entities = sorted([
        {"section": section, "entity": entity, "claims": d["claims"],
         "value_count": d["values"], "fields": sorted(d["fields"]),
         "lead_urls": sorted(d["lead_urls"])[:4]}
        for (section, entity), d in by_entity.items()
        if section in {"integrators", "distributors", "manufacturers"}
    ], key=lambda d: (-d["claims"], d["section"], d["entity"].casefold()))

    # Snapshot only: current fields and official-domain routing can help decide
    # if existing evidence may already point towards a direct supporting page.
    seeded = {}
    for section in ("manufacturers", "distributors", "integrators"):
        if intelligence is None:
            break
        lookup = {str(row.get("name") or "").casefold(): row
                  for row in intelligence.get(section) or [] if isinstance(row, dict)}
        scoped = [x for x in entities if x["section"] == section]
        seeded[section] = {"entities_with_any_public_urls": 0, "official_owned_hosts": 0}
        for item in scoped:
            row = lookup.get(item["entity"].casefold()) or {}
            evs = list(row.get("evidence") or [])
            for field in (row.get("fields") or {}).values():
                if isinstance(field, dict):
                    evs.extend(field.get("evidence") or [])
            official_hosts = {
                (urlsplit(str(ev.get("url") or "")).hostname or "").lower()
                for ev in evs if isinstance(ev, dict) and ev.get("official") is True
            }
            public_urls = {
                str(ev.get("url") or "") for ev in evs if isinstance(ev, dict)
                and str(ev.get("url") or "").startswith("https://")
            }
            seeded[section]["entities_with_any_public_urls"] += int(bool(public_urls))
            seeded[section]["official_owned_hosts"] += int(bool(official_hosts))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "backlog evidence triage only; no data accredited or gaps closed",
        "total_claims": classes["assertion"],
        "derived": classes["derive"],
        "unfilled_or_unspecified": classes["missing_or_unspecified"],
        "high_yield_claims": high_yield_claims,
        "fields": rows[:120],
        "top_companies": entities[:45],
        "existing_sources": seeded,
    }


def main() -> None:
    gaps = json.loads((ROOT / "data/current/research_gaps.json").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "data/current/intelligence.json").read_text(encoding="utf-8"))
    report = summarize(gaps, data)
    dest = ROOT / "data/current/easy_claims_triage.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        k: v for k, v in report.items()
        if k not in {"fields", "top_companies"}
    }, ensure_ascii=False))
    print("top fields:", [(x["field"], x["claims"]) for x in report["fields"][:20]])


if __name__ == "__main__":
    main()
