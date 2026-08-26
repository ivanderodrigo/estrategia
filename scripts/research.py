#!/usr/bin/env python3
"""Public evidence collector for Westcon Iberia Strategy Studio.

Scope is deliberately strict:
- public external sources only;
- no confidential/internal Westcon inputs;
- no scraping/reconstruction of licensed Gartner/Forrester/IDC reports;
- search snippets are discovery evidence and receive lower confidence;
- geography is retained explicitly.

The script is designed for GitHub Actions and writes JSON consumed by GitHub Pages.
Brave Search API is optional; without it, Google News RSS provides a smaller discovery feed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "data/base.json").read_text(encoding="utf-8"))
CFG = json.loads((ROOT / "config/research_queries.json").read_text(encoding="utf-8"))
REG = json.loads((ROOT / "config/source_registry.json").read_text(encoding="utf-8"))
CURATED = json.loads((ROOT / "data/curated_evidence.json").read_text(encoding="utf-8"))
OUT = ROOT / "data/research.latest.json"
HISTORY = ROOT / "data/history"
HISTORY.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
UA = "Westcon-Iberia-Strategy-Studio/1.2 (+public-evidence-only)"


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def source_tier(url: str) -> str:
    h = host(url)
    for tier in REG.get("tiers", []):
        for d in tier.get("domains", []):
            if h == d or h.endswith("." + d):
                return tier["id"]
    return "search-discovery"


def tier_weight(tier: str) -> int:
    for row in REG.get("tiers", []):
        if row.get("id") == tier:
            return int(row.get("weight", 50))
    return 45


def search_brave(query: str, country: str = "ES") -> list[dict]:
    key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        return []
    r = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": key, "Accept": "application/json", "User-Agent": UA},
        params={"q": query, "count": 10, "country": country if country in {"ES", "PT"} else "ALL", "search_lang": "es" if country == "ES" else "pt" if country == "PT" else "en"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    out = []
    for x in (data.get("web") or {}).get("results") or []:
        out.append({
            "title": clean(x.get("title", "")),
            "url": x.get("url", ""),
            "snippet": clean(x.get("description", "")),
            "published": x.get("page_age") or x.get("age") or "",
            "engine": "brave",
        })
    return out


def search_google_news(query: str, lang: str = "en") -> list[dict]:
    hl, gl, ceid = ("es", "ES", "ES:es") if lang == "es" else ("pt-PT", "PT", "PT:pt-150") if lang == "pt" else ("en-GB", "GB", "GB:en")
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": hl, "gl": gl, "ceid": ceid})
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception:
        return []
    out = []
    for item in root.findall(".//item")[:10]:
        out.append({
            "title": clean(item.findtext("title") or ""),
            "url": clean(item.findtext("link") or ""),
            "snippet": clean(item.findtext("description") or ""),
            "published": clean(item.findtext("pubDate") or ""),
            "engine": "google-news-rss",
        })
    return out


def infer_scope(text: str, query_country: str | None = None) -> str:
    t = text.lower()
    has_es = any(x in t for x in ["spain", "españa", "spanish", "español"])
    has_pt = any(x in t for x in ["portugal", "portuguese", "português"])
    if has_es and has_pt:
        return "Spain / Portugal"
    if has_es:
        return "Spain"
    if has_pt:
        return "Portugal"
    if any(x in t for x in ["iberia", "iberian", "península ibérica", "peninsula iberica"]):
        return "Iberia"
    if any(x in t for x in ["emea", "europe, middle east", "europe"]):
        return "Europe / EMEA"
    if query_country == "ES":
        return "Spain (query context only)"
    if query_country == "PT":
        return "Portugal (query context only)"
    return "Global / unspecified"


def confidence_for(tier: str, scope: str, engine: str) -> int:
    score = tier_weight(tier)
    if "query context only" in scope:
        score -= 18
    if engine in {"google-news-rss", "brave"} and tier == "search-discovery":
        score = min(score, 45)
    return max(20, min(100, score))


def make_queries() -> list[dict]:
    fixed = [{"query": q, "kind": "strategic", "country": "ALL"} for q in CFG.get("strategic_queries", [])]
    generated = []
    for vendor in [v["name"] for v in BASE.get("vendors", [])] + [v["name"] for v in BASE.get("externalAdditions", [])]:
        for template in CFG.get("vendor_query_templates", []):
            q = template.format(vendor=vendor)
            cc = "PT" if "Portugal" in q and "Spain" not in q else "ES" if "Spain" in q and "Portugal" not in q else "ALL"
            generated.append({"query": q, "kind": "vendor", "vendor": vendor, "country": cc})
    # Rotate vendor queries deterministically by ISO week to bound API cost while ensuring coverage.
    week = NOW.isocalendar().week
    generated.sort(key=lambda r: hashlib.sha1(f"{week}:{r['query']}".encode()).hexdigest())
    room = max(0, int(CFG.get("rotation_max_queries", 72)) - len(fixed))
    return fixed + generated[:room]



def infer_evidence_type(text: str, source_tier_name: str = "") -> str:
    """Classify a discovery row without pretending the classification proves the claim."""
    t = (text or "").lower()
    rules = [
        ("channel", ["distributor", "distribution", "mayorista", "distribuidor", "distribui", "channel partner", "channel agreement"]),
        ("analyst", ["gartner", "forrester", "idc", "omdia", "canalys", "dell'oro", "delloro", "synergy research", "magic quadrant", "wave", "marketscape"]),
        ("m&a", ["acquisition", "acquire", "acquired", "merger", "adquisición", "adquiere", "fus", "investment"]),
        ("market", ["market share", "market size", "forecast", "spending", "growth", "cuota de mercado", "mercado", "previs", "gasto"]),
        ("product", ["launch", "announces", "new product", "platform", "release", "lanz", "product update", "innovation"]),
        ("services", ["professional services", "support services", "managed services", "servicios profesionales", "soporte", "mssp", "mdr"]),
        ("partner-program", ["partner program", "partner programme", "programa de partners", "canal", "enablement", "specialization", "specialisation"]),
    ]
    if source_tier_name == "analyst-public":
        return "analyst"
    for kind, needles in rules:
        if any(n in t for n in needles):
            return kind
    return "general"


def relation_candidates(evidence: list[dict]) -> list[dict]:
    distributors = CFG.get("known_distributors", [])
    vendors = [v["name"] for v in BASE.get("vendors", [])] + [v["name"] for v in BASE.get("externalAdditions", [])]
    rows: dict[tuple[str, str, str], dict] = {}
    for e in evidence:
        text = f"{e.get('title','')} {e.get('snippet','')} {e.get('query','')}"
        low = text.lower()
        matched_vendors = [v for v in vendors if v.lower() in low]
        if e.get("vendor") and e["vendor"] not in matched_vendors:
            matched_vendors.append(e["vendor"])
        matched_dist = [d for d in distributors if d.lower() in low]
        if not matched_vendors or not matched_dist:
            continue
        scope = e.get("scope", "")
        countries = []
        if "Spain" in scope or "Iberia" in scope:
            countries.append("ES")
        if "Portugal" in scope or "Iberia" in scope:
            countries.append("PT")
        if not countries:
            continue
        for v in matched_vendors:
            for d in matched_dist:
                if d.lower() == "westcon-comstor" and v.lower() == "westcon-comstor":
                    continue
                for cc in countries:
                    key = (v, cc, d)
                    row = rows.setdefault(key, {"vendor": v, "country": cc, "distributor": d, "status": "candidate-public-signal", "confidence": 0, "evidence": []})
                    row["confidence"] = max(row["confidence"], min(88, int(e.get("confidence", 45))))
                    if e["id"] not in row["evidence"]:
                        row["evidence"].append(e["id"])
    return sorted(rows.values(), key=lambda r: (-r["confidence"], r["vendor"], r["country"], r["distributor"]))


def merge_channel_signals(*groups: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for group in groups:
        for row in group:
            key = (row.get("vendor", ""), row.get("country", ""), row.get("distributor", ""))
            if not all(key):
                continue
            cur = merged.get(key)
            if cur is None or int(row.get("confidence", 0)) > int(cur.get("confidence", 0)):
                merged[key] = dict(row)
            else:
                ev = list(dict.fromkeys((cur.get("evidence") or []) + (row.get("evidence") or [])))
                cur["evidence"] = ev
    return sorted(merged.values(), key=lambda r: (-int(r.get("confidence", 0)), r["vendor"], r["country"], r["distributor"]))


def analyst_candidates(evidence: list[dict]) -> list[dict]:
    names = CFG.get("analyst_names", [])
    out = []
    for e in evidence:
        txt = f"{e.get('title','')} {e.get('snippet','')}"
        analyst = next((a for a in names if a.lower() in txt.lower() or a.lower() in e.get("source", "").lower()), None)
        if not analyst and e.get("sourceTier") != "analyst-public":
            continue
        stats = re.findall(r"(?:\$|€)?\s?\d+(?:[.,]\d+)?\s?(?:trillion|billion|million|tn|bn|m|%)", txt, flags=re.I)
        out.append({
            "evidenceId": e["id"],
            "analyst": analyst or e.get("source", "Analyst"),
            "vendor": e.get("vendor"),
            "scope": e.get("scope"),
            "title": e.get("title"),
            "candidateStats": stats[:6],
            "confidence": e.get("confidence", 45),
            "status": "public-summary" if e.get("sourceTier") == "analyst-public" else "discovery-only",
            "evidenceType": e.get("evidenceType", "analyst"),
        })
    return out


def vendor_coverage(evidence: list[dict], channel_rows: list[dict]) -> list[dict]:
    vendors = [v["name"] for v in BASE.get("vendors", [])] + [v["name"] for v in BASE.get("externalAdditions", [])]
    result = []
    for vendor in vendors:
        rows = [e for e in evidence if (e.get("vendor") == vendor) or vendor.lower() in " ".join(map(str, e.get("tags", []))).lower() or vendor.lower() in f"{e.get('title','')} {e.get('summary','')} {e.get('snippet','')}".lower()]
        kinds = {e.get("evidenceType") or e.get("kind") for e in rows}
        analysts = {e.get("source") for e in rows if e.get("sourceTier") == "analyst-public"}
        official = {e.get("source") for e in rows if e.get("sourceTier") in {"official-company", "regulator"}}
        channel = [c for c in channel_rows if c.get("vendor") == vendor and c.get("distributor") not in {"Westcon-Comstor", "Comstor"}]
        es = any(c.get("country") in {"ES", "IBERIA"} for c in channel)
        pt = any(c.get("country") in {"PT", "IBERIA"} for c in channel)
        dimensions = {
            "channelES": es, "channelPT": pt, "analyst": bool(analysts),
            "market": "market" in kinds, "ma": "m&a" in kinds, "product": "product" in kinds,
            "services": "services" in kinds or "partner-program" in kinds,
        }
        score = round(sum(1 for x in dimensions.values() if x) / len(dimensions) * 100)
        result.append({
            "vendor": vendor, "coverage": score, "dimensions": dimensions,
            "evidenceCount": len(rows), "analystSources": sorted(x for x in analysts if x),
            "officialSources": sorted(x for x in official if x), "alternativeChannelSignals": len(channel),
        })
    return sorted(result, key=lambda x: (x["coverage"], x["vendor"]))


def research_gaps(coverage: list[dict]) -> list[dict]:
    labels = {"channelES":"mayoristas alternativos en España", "channelPT":"mayoristas alternativos en Portugal", "analyst":"señal pública de analistas", "market":"tamaño/crecimiento de mercado", "ma":"M&A / cambio estratégico", "product":"novedades de plataforma/producto", "services":"servicios/programa de canal"}
    out=[]
    for row in coverage:
        missing=[labels[k] for k,v in row["dimensions"].items() if not v]
        if missing:
            out.append({"vendor":row["vendor"],"coverage":row["coverage"],"missing":missing,"priority":"P0" if row["coverage"]<30 else "P1" if row["coverage"]<55 else "P2"})
    return out


def signal_stats(evidence: list[dict]) -> dict:
    by_tier={} ; by_type={} ; by_scope={} ; by_source={}
    for e in evidence:
        by_tier[e.get("sourceTier","unknown")]=by_tier.get(e.get("sourceTier","unknown"),0)+1
        typ=e.get("evidenceType") or e.get("kind") or "general"; by_type[typ]=by_type.get(typ,0)+1
        scope=e.get("scope") or "unknown"; by_scope[scope]=by_scope.get(scope,0)+1
        src=e.get("source") or "unknown"; by_source[src]=by_source.get(src,0)+1
    return {"byTier":by_tier,"byType":by_type,"byScope":by_scope,"topSources":sorted(by_source.items(), key=lambda x:(-x[1],x[0]))[:20]}


def main() -> None:
    queries = make_queries()
    brave = bool(os.getenv("BRAVE_SEARCH_API_KEY", "").strip())
    if not brave:
        # Keep the zero-secret fallback polite and lightweight. Strategic queries + a small weekly vendor rotation.
        strategic = [q for q in queries if q.get("kind") == "strategic"]
        vendor = [q for q in queries if q.get("kind") == "vendor"][:48]
        queries = strategic + vendor
    evidence: list[dict] = [dict(e, curated=True) for e in CURATED.get("evidence", [])]
    seen = {hashlib.sha1((e.get("title", "") + "|" + (e.get("url") or "")).encode()).hexdigest() for e in evidence}
    for qrow in queries:
        q = qrow["query"]
        rows: list[dict] = []
        if brave:
            try:
                rows.extend(search_brave(q, qrow.get("country", "ALL")))
            except Exception as exc:
                print(f"Brave error for {q!r}: {exc}")
        # News RSS is always used for strategic queries; without Brave, it is also the fallback for vendor queries.
        if qrow.get("kind") == "strategic" or not brave:
            lang = "pt" if qrow.get("country") == "PT" else "es" if qrow.get("country") == "ES" else "en"
            rows.extend(search_google_news(q, lang))
        for x in rows:
            url = x.get("url") or ""
            fp = hashlib.sha1((x.get("title", "") + "|" + url).encode()).hexdigest()
            if fp in seen:
                continue
            seen.add(fp)
            tier = source_tier(url)
            scope = infer_scope(f"{x.get('title','')} {x.get('snippet','')} {q}", qrow.get("country"))
            evidence.append({
                "id": fp[:14],
                "title": x.get("title"),
                "url": url,
                "source": host(url) or x.get("engine"),
                "sourceTier": tier,
                "evidenceType": infer_evidence_type(f"{x.get('title','')} {x.get('snippet','')} {q}", tier),
                "scope": scope,
                "kind": qrow.get("kind"),
                "vendor": qrow.get("vendor"),
                "query": q,
                "snippet": x.get("snippet"),
                "published": x.get("published"),
                "engine": x.get("engine"),
                "confidence": confidence_for(tier, scope, x.get("engine", "")),
                "collectedAt": NOW.isoformat(),
                "validationState": "primary/public source" if tier in {"regulator", "official-company", "analyst-public"} else "discovery; validate before executive use",
            })
        if brave:
            time.sleep(0.12)

    channels = merge_channel_signals(CURATED.get("channelSignals", []), relation_candidates(evidence))
    coverage = vendor_coverage(evidence, channels)
    analysts = analyst_candidates(evidence)
    payload = {
        "generatedAt": NOW.isoformat(),
        "mode": "automated-public-research-v2",
        "queryCount": len(queries),
        "braveEnabled": brave,
        "notice": "Public external research only. No internal/confidential Westcon data. Discovery is separated from executive evidence; geography and confidence are preserved.",
        "evidence": evidence,
        "channelSignals": channels,
        "analystSignals": analysts,
        "coverage": coverage,
        "gaps": research_gaps(coverage),
        "derived": {
            "evidenceCount": len(evidence),
            "officialOrAnalystCount": sum(1 for e in evidence if e.get("sourceTier") in {"official-company", "regulator", "analyst-public"}),
            "channelSignalCount": len(channels),
            "analystSignalCount": len(analysts),
            "statistics": signal_stats(evidence),
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (HISTORY / f"research-{TODAY}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(evidence)} evidence rows from {len(queries)} queries -> {OUT}")


if __name__ == "__main__":
    main()
