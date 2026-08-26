#!/usr/bin/env python3
"""Deep public-intelligence collector for Westcon Iberia Strategy Studio v1.4.

Design goals
------------
* Public external information only.
* Preserve geography (ES/PT/Iberia/EMEA/global) and confidence.
* Separate discovery from executive-grade evidence.
* Search broadly, then de-duplicate and corroborate.
* Exploit no-key public sources (TED, GDELT, Arquivo.pt, official sitemaps,
  Spanish procurement open data, dados.gov.pt) in addition to optional Brave.
* Never scrape/reconstruct licensed Gartner/Forrester/IDC content.
* Prioritise research gaps automatically.

The output remains static JSON so the application can run entirely on GitHub Pages.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import io
import json
import os
import pathlib
import random
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
import math
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

try:
    import openpyxl
except Exception:
    openpyxl = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "data/base.json").read_text(encoding="utf-8"))
CFG = json.loads((ROOT / "config/research_queries.json").read_text(encoding="utf-8"))
REG = json.loads((ROOT / "config/source_registry.json").read_text(encoding="utf-8"))
DEEP = json.loads((ROOT / "config/deep_research.json").read_text(encoding="utf-8"))
CURATED = json.loads((ROOT / "data/curated_evidence.json").read_text(encoding="utf-8"))
ECOSYSTEM = json.loads((ROOT / "data/ecosystem.json").read_text(encoding="utf-8"))
VENDOR_INTEL = json.loads((ROOT / "data/vendor_intelligence.json").read_text(encoding="utf-8"))
OUT = ROOT / "data/research.latest.json"
STATUS_OUT = ROOT / "data/research_status.json"
CHANGES_OUT = ROOT / "data/changes.latest.json"
HISTORY = ROOT / "data/history"
HISTORY.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
PROFILE = os.getenv("RESEARCH_PROFILE", "deep").strip().lower()
for _arg in os.sys.argv[1:]:
    if _arg.startswith("--profile="):
        PROFILE = _arg.split("=", 1)[1].strip().lower()
if PROFILE not in DEEP.get("profiles", {}):
    PROFILE = "deep"
PROFILE_CFG = DEEP.get("profiles", {}).get(PROFILE, {})
BUDGETS = dict(DEEP.get("budgets", {}))
BUDGETS.update(PROFILE_CFG.get("budgets", {}))
UA = f"Westcon-Iberia-Strategy-Studio/1.4 ({PROFILE}; public-intelligence-only)"
TIMEOUT = int(BUDGETS.get("request_timeout_seconds", 25))
WORKERS = int(BUDGETS.get("http_workers", 12))

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9,pt;q=0.8,en;q=0.7"})


def clean(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm(text: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(text or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


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


def sha(*parts: str) -> str:
    return hashlib.sha1("|".join(str(x or "") for x in parts).encode("utf-8", "ignore")).hexdigest()


def get_json(url: str, **kwargs):
    r = SESSION.get(url, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r.json()


def active_vendor_names() -> list[str]:
    return [v["name"] for v in BASE.get("vendors", [])]


def tracked_names() -> list[str]:
    names = active_vendor_names()
    names += [v.get("name") for v in BASE.get("externalAdditions", []) if v.get("name")]
    names += [v.get("name") for v in BASE.get("externalCompetitors", []) if v.get("name")]
    names += CFG.get("tracked_competitors", [])
    return list(dict.fromkeys(names))


def aliases_for(vendor: str) -> list[str]:
    aliases = CFG.get("vendor_aliases", {}).get(vendor, [vendor])
    return list(dict.fromkeys([vendor, *aliases]))


def infer_scope(text: str, query_country: str | None = None) -> str:
    t = norm(text)
    has_es = any(x in t for x in ["spain", "espana", "spanish", "madrid", "barcelona"])
    has_pt = any(x in t for x in ["portugal", "portuguese", "portugues", "lisboa", "porto"])
    if has_es and has_pt:
        return "Spain / Portugal"
    if has_es:
        return "Spain"
    if has_pt:
        return "Portugal"
    if any(x in t for x in ["iberia", "iberian", "peninsula iberica"]):
        return "Iberia"
    if any(x in t for x in ["emea", "europe", "europa"]):
        return "Europe / EMEA"
    if query_country == "ES":
        return "Spain (query context only)"
    if query_country == "PT":
        return "Portugal (query context only)"
    return "Global / unspecified"


def confidence_for(tier: str, scope: str, engine: str, directness: int = 0) -> int:
    score = tier_weight(tier)
    if "query context only" in scope:
        score -= 18
    if engine in {"brave", "google-news-rss"} and tier == "search-discovery":
        score = min(score, 45)
    if engine == "gdelt":
        score = min(score, 58 if tier == "search-discovery" else tier_weight(tier))
    if engine == "arquivo-pt":
        score = min(score, 68 if tier == "search-discovery" else tier_weight(tier))
    score += directness
    return max(20, min(100, score))


def infer_evidence_type(text: str, source_tier_name: str = "") -> str:
    t = norm(text)
    rules = [
        ("procurement", ["tender", "award", "contract", "licitacion", "adjudicacion", "contrato", "concurso publico", "winner"]),
        ("channel", ["distributor", "distribution", "mayorista", "distribuidor", "linecard", "partner locator", "authorized distributor"]),
        ("analyst", ["gartner", "forrester", "idc", "omdia", "canalys", "dell oro", "synergy research", "magic quadrant", "wave", "marketscape"]),
        ("m&a", ["acquisition", "acquire", "acquired", "merger", "adquisicion", "adquiere", "fusion", "investment"]),
        ("market", ["market share", "market size", "forecast", "spending", "growth", "cuota de mercado", "mercado", "prevision", "gasto"]),
        ("competitive", ["competitor", "alternative", "replacement", "migration", "versus", "competitive displacement", "tco", "roi"]),
        ("customer", ["customer story", "case study", "customer success", "caso de exito", "caso de cliente", "deployment", "implementation"]),
        ("integrator", ["system integrator", "integrator", "integrador", "partner of the year", "solution provider", "mssp", "certified partner", "implementation partner"]),
        ("services", ["professional services", "support services", "managed services", "servicios profesionales", "soporte", "mssp", "mdr", "lifecycle"]),
        ("partner-program", ["partner program", "partner programme", "programa de partners", "enablement", "specialization", "specialisation", "academy"]),
        ("product", ["launch", "announces", "new product", "platform", "release", "lanzamiento", "product update", "innovation", "roadmap"]),
    ]
    if source_tier_name == "analyst-public":
        return "analyst"
    for kind, needles in rules:
        if any(n in t for n in needles):
            return kind
    return "general"


# ----------------------------- Search engines -----------------------------

def search_brave(qrow: dict) -> list[dict]:
    key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        return []
    country = qrow.get("country", "ALL")
    params = {
        "q": qrow["query"],
        "count": 10,
        "country": country if country in {"ES", "PT"} else "ALL",
        "search_lang": "es" if country == "ES" else "pt" if country == "PT" else "en",
        "safesearch": "moderate",
        "text_decorations": False,
    }
    r = SESSION.get("https://api.search.brave.com/res/v1/web/search", headers={"X-Subscription-Token": key, "Accept": "application/json"}, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for x in (r.json().get("web") or {}).get("results") or []:
        out.append({"title": clean(x.get("title")), "url": x.get("url", ""), "snippet": clean(x.get("description")), "published": x.get("page_age") or x.get("age") or "", "engine": "brave"})
    return out


def search_google_news(qrow: dict) -> list[dict]:
    country = qrow.get("country")
    lang = "pt" if country == "PT" else "es" if country == "ES" else "en"
    hl, gl, ceid = ("es", "ES", "ES:es") if lang == "es" else ("pt-PT", "PT", "PT:pt-150") if lang == "pt" else ("en-GB", "GB", "GB:en")
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": qrow["query"], "hl": hl, "gl": gl, "ceid": ceid})
    try:
        r = SESSION.get(url, timeout=TIMEOUT); r.raise_for_status(); root = ET.fromstring(r.text)
    except Exception:
        return []
    out = []
    for item in root.findall(".//item")[:12]:
        out.append({"title": clean(item.findtext("title")), "url": clean(item.findtext("link")), "snippet": clean(item.findtext("description")), "published": clean(item.findtext("pubDate")), "engine": "google-news-rss"})
    return out


def search_gdelt(qrow: dict) -> list[dict]:
    # GDELT DOC 2.0 is public/no-key. Constrain queries to avoid broad noisy results.
    query = qrow["query"]
    try:
        data = get_json(DEEP["engines"]["gdelt"]["endpoint"], params={"query": query, "mode": "ArtList", "maxrecords": 50, "format": "json", "sort": "HybridRel"})
    except Exception:
        return []
    out = []
    for x in data.get("articles", [])[:50]:
        out.append({"title": clean(x.get("title")), "url": x.get("url", ""), "snippet": clean(x.get("seendate", "") + " " + x.get("domain", "")), "published": x.get("seendate", ""), "engine": "gdelt", "sourcecountry": x.get("sourcecountry"), "language": x.get("language")})
    return out


def search_arquivo(qrow: dict) -> list[dict]:
    # Useful for historic distribution/partner changes, particularly Portugal.
    try:
        data = get_json(DEEP["engines"]["arquivo_pt"]["endpoint"], params={"q": qrow["query"], "maxItems": 50, "prettyPrint": "false"})
    except Exception:
        return []
    out = []
    for x in (data.get("response_items") or data.get("responseItems") or [])[:50]:
        out.append({"title": clean(x.get("title")), "url": x.get("originalURL") or x.get("linkToArchive") or x.get("url") or "", "snippet": clean(x.get("snippet") or x.get("linkToArchive") or ""), "published": x.get("tstamp") or x.get("date") or "", "engine": "arquivo-pt"})
    return out


# ----------------------------- Official sitemaps -----------------------------

def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    urls, maps = [], []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return urls, maps
    tag = root.tag.lower()
    if tag.endswith("sitemapindex"):
        for loc in root.findall(".//{*}loc"):
            if loc.text: maps.append(loc.text.strip())
    else:
        for loc in root.findall(".//{*}loc"):
            if loc.text: urls.append(loc.text.strip())
    return urls, maps


def discover_sitemap_urls(domain: str, max_urls: int = 120) -> list[str]:
    seeds = [f"https://{domain}/sitemap.xml", f"https://www.{domain}/sitemap.xml", f"https://{domain}/sitemap_index.xml"]
    seen_maps, urls = set(), []
    queue = list(seeds)
    while queue and len(urls) < max_urls:
        sm = queue.pop(0)
        if sm in seen_maps: continue
        seen_maps.add(sm)
        try:
            r = SESSION.get(sm, timeout=TIMEOUT); r.raise_for_status()
            us, ms = parse_sitemap(r.text)
        except Exception:
            continue
        urls.extend(us)
        queue.extend(ms[:12])
        if len(seen_maps) > 18: break
    high = CFG.get("high_value_official_paths", [])
    def score(u: str) -> int:
        lu = u.lower(); return sum(4 for x in high if x in lu) + sum(2 for x in ["spain","es-es","/es/","portugal","pt-pt","/pt/","iberia"] if x in lu)
    return sorted(list(dict.fromkeys(urls)), key=lambda u: (-score(u), u))[:max_urls]


def fetch_page_metadata(url: str) -> dict | None:
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", "text/html"): return None
        text = r.text[:400000]
        mt = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        md = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\'](.*?)["\']', text, re.I | re.S)
        if not md:
            md = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']', text, re.I | re.S)
        return {"title": clean(mt.group(1) if mt else url.rsplit("/",1)[-1]), "snippet": clean(md.group(1) if md else ""), "url": r.url, "published": "", "engine": "official-sitemap"}
    except Exception:
        return None


def official_sitemap_evidence(vendors: list[str]) -> list[dict]:
    domains = CFG.get("vendor_domains", {})
    budget = int(BUDGETS.get("sitemap_pages_max", 1400))
    per_vendor = max(12, min(55, budget // max(1, len(vendors))))
    targets = []
    for vendor in vendors:
        domain = domains.get(vendor)
        if not domain: continue
        for u in discover_sitemap_urls(domain, per_vendor):
            lu = u.lower()
            if any(x in lu for x in CFG.get("high_value_official_paths", [])):
                targets.append((vendor, u))
    targets = targets[:budget]
    out = []
    with ThreadPoolExecutor(max_workers=min(WORKERS, 12)) as ex:
        futs = {ex.submit(fetch_page_metadata, u):(v,u) for v,u in targets}
        for fut in as_completed(futs):
            vendor, u = futs[fut]
            try: row = fut.result()
            except Exception: row = None
            if not row: continue
            row.update({"vendor": vendor, "country": "ALL", "kind": "official-crawl"})
            out.append(row)
    return out



# ----------------------------- Ecosystem / analyst official crawls -----------------------------

def infer_country_from_url(url: str) -> str | None:
    u = url.lower()
    es = any(x in u for x in ["/es/", "/es-es/", ".es/", "spain", "espana"])
    pt = any(x in u for x in ["/pt/", "/pt-pt/", ".pt/", "portugal"])
    if es and not pt: return "ES"
    if pt and not es: return "PT"
    return None


def official_entity_sitemap_evidence(entity_domains: dict, entity_kind: str, budget: int) -> list[dict]:
    if not entity_domains or budget <= 0: return []
    per_entity = max(8, min(55, budget // max(1, len(entity_domains))))
    vendor_terms = [(v, [norm(a) for a in aliases_for(v) if len(norm(a)) >= 3]) for v in tracked_names()]
    targets=[]
    for entity, domain in entity_domains.items():
        for u in discover_sitemap_urls(domain, per_entity):
            lu=u.lower()
            if any(x in lu for x in CFG.get('high_value_official_paths',[])):
                targets.append((entity,u))
    targets=targets[:budget]
    out=[]
    with ThreadPoolExecutor(max_workers=min(WORKERS,12)) as ex:
        futs={ex.submit(fetch_page_metadata,u):(entity,u) for entity,u in targets}
        for fut in as_completed(futs):
            entity,u=futs[fut]
            try: row=fut.result()
            except Exception: row=None
            if not row: continue
            text=norm(f"{row.get('title','')} {row.get('snippet','')} {row.get('url','')}")
            matches=[]
            for vendor,terms in vendor_terms:
                if any(t and t in text for t in terms[:5]): matches.append(vendor)
            if not matches: continue
            cc=infer_country_from_url(row.get('url',''))
            for vendor in matches[:4]:
                r=dict(row)
                r.update({'vendor':vendor,'country':cc or 'ALL','kind':f'official-{entity_kind}-crawl','engine':'official-ecosystem-sitemap','sourceEntity':entity})
                r['snippet']=clean(f"{entity_kind}: {entity}. {r.get('snippet','')}")
                if entity_kind=='integrator': r['winner']=entity
                out.append(r)
    return out


def official_analyst_sitemap_evidence(budget: int) -> list[dict]:
    domains=CFG.get('analyst_domains',{})
    if not domains or budget<=0: return []
    per=max(10,min(50,budget//max(1,len(domains))))
    keywords=['2026','market','forecast','security','cyber','network','sase','endpoint','identity','cloud','ai','automation','lan','wlan','ndr','ot','data center','market share']
    vendor_terms=[(v,[norm(a) for a in aliases_for(v)[:4]]) for v in tracked_names()]
    out=[]; targets=[]
    for analyst,domain in domains.items():
        for u in discover_sitemap_urls(domain,per):
            if any(k.replace(' ','-') in u.lower() or k in u.lower() for k in keywords): targets.append((analyst,u))
    targets=targets[:budget]
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(fetch_page_metadata,u):(a,u) for a,u in targets}
        for fut in as_completed(futs):
            analyst,u=futs[fut]
            try: row=fut.result()
            except Exception: row=None
            if not row: continue
            text=norm(f"{row.get('title','')} {row.get('snippet','')} {row.get('url','')}")
            if not any(norm(k) in text for k in keywords): continue
            matched=[v for v,terms in vendor_terms if any(t and t in text for t in terms)]
            if matched:
                for vendor in matched[:4]:
                    r=dict(row); r.update({'vendor':vendor,'country':'ALL','kind':'analyst-official-crawl','engine':'official-analyst-sitemap'}); out.append(r)
            else:
                r=dict(row); r.update({'vendor':None,'country':'ALL','kind':'analyst-official-crawl','engine':'official-analyst-sitemap'}); out.append(r)
    return out


def load_previous_payload() -> dict:
    try: return json.loads(OUT.read_text(encoding='utf-8'))
    except Exception: return {}


def carryover_evidence(prev: dict) -> list[dict]:
    days=int(BUDGETS.get('carryover_days',730)); cutoff=NOW-dt.timedelta(days=days); out=[]
    for e in prev.get('evidence',[]):
        if e.get('curated'): continue
        raw=e.get('collectedAt') or e.get('published')
        keep=True
        if raw:
            try:
                d=dt.datetime.fromisoformat(str(raw).replace('Z','+00:00'))
                if not d.tzinfo: d=d.replace(tzinfo=dt.timezone.utc)
                keep=d>=cutoff
            except Exception: keep=True
        if keep: out.append(e)
    return out


def _relset(rows: list[dict], kind: str) -> set[tuple]:
    if kind=='channel': return {(r.get('vendor'),r.get('country'),norm(r.get('distributor'))) for r in rows if r.get('vendor') and r.get('country') and r.get('distributor') and int(r.get('confidence',0))>=70}
    return {(r.get('vendor'),r.get('country'),norm(r.get('name'))) for r in rows if r.get('vendor') and r.get('country') and r.get('name') and int(r.get('confidence',0))>=70}


def compute_changes(prev: dict, channels, integrators, customers, coverage) -> list[dict]:
    changes=[]
    for kind,label,newrows,oldrows in [
        ('channel','Nuevo mayorista / señal de canal',channels,prev.get('channelSignals',[])),
        ('integrator','Nuevo integrador / partner',integrators,prev.get('integratorSignals',[])),
        ('customer','Nueva referencia pública / cliente',customers,prev.get('customerSignals',[]))]:
        old=_relset(oldrows,kind); new=_relset(newrows,kind)
        for key in sorted(new-old)[:120]:
            vendor,country,name=key
            row=next((r for r in newrows if r.get('vendor')==vendor and r.get('country')==country and norm(r.get('distributor' if kind=='channel' else 'name'))==name),{})
            changes.append({'type':kind,'vendor':vendor,'country':country,'title':label,'entity':row.get('distributor') if kind=='channel' else row.get('name'),'confidence':row.get('confidence'),'url':row.get('url'),'detectedAt':NOW.isoformat()})
    prev_cov={r.get('vendor'):int(r.get('coverage',0)) for r in prev.get('coverage',[]) if r.get('vendor')}
    delta_min=int(DEEP.get('change_detection',{}).get('material_coverage_delta',8))
    for r in coverage:
        if r['vendor'] in prev_cov and abs(r['coverage']-prev_cov[r['vendor']])>=delta_min:
            changes.append({'type':'coverage','vendor':r['vendor'],'title':'Cambio material de cobertura de inteligencia','from':prev_cov[r['vendor']],'to':r['coverage'],'detectedAt':NOW.isoformat()})
    return changes[:250]


def detect_conflicts(evidence: list[dict], channels: list[dict]) -> list[dict]:
    terms=[norm(x) for x in DEEP.get('change_detection',{}).get('conflict_terms',[])]
    out=[]
    for e in evidence:
        text=norm(f"{e.get('title','')} {e.get('snippet','')}")
        if not any(t and t in text for t in terms): continue
        vendor=e.get('vendor')
        if not vendor: continue
        impacted=[c for c in channels if c.get('vendor')==vendor and (not e.get('country') or c.get('country')==e.get('country'))]
        out.append({'vendor':vendor,'country':e.get('country'),'title':e.get('title'),'url':e.get('url'),'evidenceId':e.get('id'),'possibleConflictWith':[f"{x.get('country')}:{x.get('distributor')}" for x in impacted[:8]],'status':'needs-validation'})
    return out[:120]


def write_light_history(payload: dict, changes: list[dict]) -> None:
    snap={'generatedAt':payload.get('generatedAt'),'profile':PROFILE,'derived':payload.get('derived'),'coverage':payload.get('coverage'),'gaps':payload.get('gaps'),'changes':changes,'conflicts':payload.get('conflicts',[])}
    path=HISTORY/f"snapshot-{TODAY}-{PROFILE}.json"; path.write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8')
    # Keep repository history bounded.
    files=sorted(HISTORY.glob(f"snapshot-*-{PROFILE}.json"), key=lambda x:x.name, reverse=True)
    keep=int(DEEP.get('history',{}).get('light_snapshots_daily' if PROFILE=='daily' else 'light_snapshots_deep',30))
    for old in files[keep:]:
        try: old.unlink()
        except Exception: pass


def parse_date_any(value: str):
    raw=clean(value)
    if not raw: return None
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%Y/%m/%d","%a, %d %b %Y %H:%M:%S %Z"):
        try: return dt.datetime.strptime(raw[:32],fmt).date()
        except Exception: pass
    m=re.search(r"(20\\d{2})[-/](\\d{1,2})[-/](\\d{1,2})",raw)
    if m:
        try: return dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
        except Exception: pass
    return None


def freshness_bonus(value: str) -> int:
    d=parse_date_any(value)
    if not d: return 0
    age=max(0,(NOW.date()-d).days)
    if age<=90: return 6
    if age<=365: return 4
    if age<=730: return 1
    if age>1460: return -7
    if age>1095: return -4
    return -1


def extract_named_field(flat: dict[str,str], needles: list[str]) -> str:
    scored=[]
    for k,v in flat.items():
        nk=norm(k)
        for i,n in enumerate(needles):
            if norm(n) in nk and clean(v): scored.append((100-i*4-len(k)*0.001,clean(v)))
    return max(scored,default=(0,''))[1]


def match_vendors_text(text: str, vendors: list[str]) -> list[str]:
    nt=norm(text)
    out=[]
    for v in vendors:
        aliases=[norm(a) for a in aliases_for(v)]
        # Require explicit vendor/platform token; ignore very short ambiguous aliases.
        if any(a and len(a)>=4 and re.search(rf"(?:^|\\s){re.escape(a)}(?:$|\\s)",f" {nt} ") for a in aliases): out.append(v)
    return out


def match_integrators_text(text: str) -> list[str]:
    nt=norm(text)
    return [x for x in CFG.get('known_integrators',[]) if len(norm(x))>=3 and norm(x) in nt]

# ----------------------------- Procurement intelligence -----------------------------

def flatten_json(obj, prefix="") -> dict[str, str]:
    out = {}
    if isinstance(obj, dict):
        for k,v in obj.items(): out.update(flatten_json(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i,v in enumerate(obj[:20]): out.update(flatten_json(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = clean(obj)
    return out


def ted_search(vendor: str, country: str) -> list[dict]:
    code = DEEP.get("public_procurement", {}).get("ted", {}).get("countries", {}).get(country)
    if not code: return []
    alias = aliases_for(vendor)[0]
    query = f'FT~"{alias}" AND CY={code}'
    body = {"query": query, "fields": DEEP["public_procurement"]["ted"]["fields"], "page": 1, "limit": 100, "scope": "ALL", "checkQuerySyntax": False, "paginationMode": "PAGE_NUMBER"}
    try:
        r = SESSION.post(DEEP["engines"]["ted"]["endpoint"], json=body, timeout=TIMEOUT); r.raise_for_status(); data = r.json()
    except Exception:
        return []
    records = data.get("notices") or data.get("results") or data.get("items") or []
    out = []
    for rec in records[:100]:
        flat = flatten_json(rec)
        title = next((v for k,v in flat.items() if "notice-title" in k or "contract-title" in k), "TED procurement notice")
        buyer = next((v for k,v in flat.items() if "buyer-name" in k and v), "")
        winner = next((v for k,v in flat.items() if "winner-name" in k and v), "")
        pubno = next((v for k,v in flat.items() if "publication-number" in k and v), "")
        url = f"https://ted.europa.eu/en/notice/{pubno}/html" if pubno else "https://ted.europa.eu/"
        snippet = clean(f"Buyer: {buyer}. Winner: {winner}. Vendor search: {vendor}.")
        out.append({"title": title, "url": url, "snippet": snippet, "published": "", "engine": "ted", "vendor": vendor, "country": country, "buyer": buyer, "winner": winner, "procurement": True})
    return out


def parse_atom_entries(xml_bytes: bytes) -> list[str]:
    try: root = ET.fromstring(xml_bytes)
    except Exception: return []
    rows=[]
    for entry in root.findall(".//{*}entry"):
        rows.append(clean(ET.tostring(entry, encoding="unicode")))
    return rows


def discover_official_links(page_url: str, extensions=(".xlsx",".zip",".csv")) -> list[str]:
    try:
        r=SESSION.get(page_url,timeout=TIMEOUT); r.raise_for_status(); text=r.text
    except Exception:
        return []
    hrefs=re.findall(r'href=["\\\']([^"\\\']+)["\\\']',text,flags=re.I)
    out=[]
    for h in hrefs:
        u=urllib.parse.urljoin(r.url,h.replace('&amp;','&'))
        path=urlparse(u).path.lower()
        if any(ext in path for ext in extensions): out.append(u)
    return list(dict.fromkeys(out))


def xlsx_procurement_scan(content: bytes, vendors: list[str], country: str, source_url: str, engine: str) -> list[dict]:
    if openpyxl is None: return []
    try:
        wb=openpyxl.load_workbook(io.BytesIO(content),read_only=True,data_only=True)
    except Exception:
        return []
    out=[]
    for ws in wb.worksheets[:6]:
        rows=ws.iter_rows(values_only=True)
        try: header=[clean(x) for x in next(rows)]
        except StopIteration: continue
        nh=[norm(x) for x in header]
        def idx(words):
            for i,h in enumerate(nh):
                if any(norm(w) in h for w in words): return i
            return None
        i_title=idx(['objeto','titulo','title','descricao','descripción','denominacion'])
        i_buyer=idx(['organo de contratacion','entidad adjudicadora','adjudicante','buyer','entidade adjudicante'])
        i_winner=idx(['adjudicatario','contratista','winner','fornecedor','cocontratante'])
        i_date=idx(['fecha adjudicacion','fecha publicacion','date','data publicacao','data celebracao'])
        i_url=idx(['url','enlace','link','uri'])
        for ridx,row in enumerate(rows):
            if ridx>350000: break
            vals=[clean(x) for x in row]
            blob=' | '.join(vals)
            matched=match_vendors_text(blob,vendors)
            if not matched: continue
            ints=match_integrators_text(blob)
            title=vals[i_title] if i_title is not None and i_title<len(vals) else 'Contratación pública'
            buyer=vals[i_buyer] if i_buyer is not None and i_buyer<len(vals) else ''
            winner=vals[i_winner] if i_winner is not None and i_winner<len(vals) else (ints[0] if ints else '')
            date=vals[i_date] if i_date is not None and i_date<len(vals) else ''
            url=vals[i_url] if i_url is not None and i_url<len(vals) and vals[i_url].startswith('http') else source_url
            for vendor in matched:
                out.append({'title':title or 'Contratación pública','url':url,'snippet':clean(blob[:2200]),'published':date,'engine':engine,'vendor':vendor,'country':country,'procurement':True,'winner':winner,'buyer':buyer,'integrators':ints})
                if len(out)>=2200: return out
    return out


def official_spain_procurement_rows(vendors: list[str]) -> list[dict]:
    """Use current official PLACSP open data, preferring XLSX and then technical Atom ZIP feeds."""
    year=NOW.year
    catalog=DEEP.get('public_procurement',{}).get('spain',{}).get('catalog_page')
    links=discover_official_links(catalog,(".xlsx",".zip"))
    # Current/updated files first; avoid archives unrelated to current intelligence.
    links.sort(key=lambda u:(str(year) in u, 'xlsx' in u.lower(), 'licit' in norm(u)),reverse=True)
    out=[]
    for url in links[:6]:
        try:
            r=SESSION.get(url,timeout=70); r.raise_for_status(); content=r.content
            if len(content)>140_000_000: continue
        except Exception: continue
        if content[:2]==b'PK' and (url.lower().endswith('.xlsx') or b'[Content_Types].xml' in content[:8000]):
            out.extend(xlsx_procurement_scan(content,vendors,'ES',url,'placsp-xlsx-open-data'))
            continue
        try: z=zipfile.ZipFile(io.BytesIO(content))
        except Exception: continue
        for name in z.namelist()[:160]:
            if not name.lower().endswith(('.atom','.xml')): continue
            try: rows=parse_atom_entries(z.read(name))
            except Exception: continue
            for text in rows:
                matched=match_vendors_text(text,vendors)
                if not matched: continue
                flat={'entry':clean(text)}
                buyer=extract_named_field(flat,['buyer','contracting','adjudicador'])
                ints=match_integrators_text(text)
                title_match=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
                id_match=re.search(r'<id[^>]*>(.*?)</id>',text,re.I|re.S)
                upd_match=re.search(r'<updated[^>]*>(.*?)</updated>',text,re.I|re.S)
                for vendor in matched:
                    out.append({'title':clean(title_match.group(1) if title_match else 'PLACSP procurement signal'),'url':clean(id_match.group(1) if id_match else catalog),'snippet':clean(text[:2200]),'published':clean(upd_match.group(1) if upd_match else ''),'engine':'placsp-open-data','vendor':vendor,'country':'ES','procurement':True,'winner':ints[0] if ints else '','buyer':buyer,'integrators':ints})
                    if len(out)>=2200:return out
    return out

def dados_gov_pt_contract_rows(vendors: list[str]) -> list[dict]:
    """Read public Portal BASE / IMPIC contract datasets via dados.gov.pt resources."""
    endpoint=DEEP.get('engines',{}).get('dados_gov_pt',{}).get('endpoint')
    q=DEEP.get('public_procurement',{}).get('portugal',{}).get('dataset_query','Contratos Públicos Portal Base IMPIC contratos')
    try: data=get_json(endpoint,params={'q':q,'page_size':20})
    except Exception:return []
    resources=[]
    for ds in data.get('data',[])[:8]:
        title=norm(ds.get('title',''))
        if 'contrato' not in title: continue
        for res in ds.get('resources') or []:
            rr=dict(res); rr['_dataset_title']=ds.get('title',''); resources.append(rr)
    def rscore(r):
        s=norm(f"{r.get('title','')} {r.get('url','')} {r.get('format','')}")
        return (35 if str(NOW.year) in s else 0)+(25 if 'json' in s else 0)+(22 if 'csv' in s else 0)+(18 if 'xlsx' in s else 0)+(10 if 'zip' in s else 0)
    resources=sorted(resources,key=rscore,reverse=True)[:10]
    out=[]
    for res in resources:
        url=res.get('url') or res.get('latest')
        if not url: continue
        try:
            r=SESSION.get(url,timeout=80);r.raise_for_status();content=r.content
            if len(content)>160_000_000:continue
        except Exception:continue
        # XLSX
        if url.lower().endswith('.xlsx') or (content[:2]==b'PK' and b'[Content_Types].xml' in content[:8000]):
            out.extend(xlsx_procurement_scan(content,vendors,'PT',url,'dados-gov-pt-xlsx'))
            if len(out)>=2200:return out[:2200]
            continue
        blobs=[]
        if content[:2]==b'PK':
            try:
                z=zipfile.ZipFile(io.BytesIO(content))
                for n in z.namelist()[:30]:
                    if n.lower().endswith(('.csv','.json','.jsonl')):blobs.append((n,z.read(n)))
            except Exception: pass
        else: blobs=[(url,content)]
        for name,blob in blobs:
            lower=name.lower()
            if lower.endswith(('.json','.jsonl')):
                try:
                    obj=json.loads(blob.decode('utf-8','ignore'))
                    records=obj if isinstance(obj,list) else obj.get('data') or obj.get('results') or []
                except Exception: records=[]
                for rec in records[:500000]:
                    flat=flatten_json(rec); blobtxt=' | '.join(flat.values()); matched=match_vendors_text(blobtxt,vendors)
                    if not matched:continue
                    buyer=extract_named_field(flat,['adjudicante','buyer','entidade','contracting'])
                    winner=extract_named_field(flat,['adjudicatario','cocontratante','fornecedor','winner'])
                    title=extract_named_field(flat,['objeto','descricao','description','title']) or 'Portal BASE / IMPIC public contract'
                    date=extract_named_field(flat,['data publicacao','data celebracao','date'])
                    for vendor in matched:
                        out.append({'title':title,'url':url,'snippet':clean(blobtxt[:2200]),'published':date,'engine':'dados-gov-pt','vendor':vendor,'country':'PT','procurement':True,'winner':winner,'buyer':buyer,'integrators':match_integrators_text(blobtxt)})
                        if len(out)>=2200:return out
            else:
                text=blob.decode('utf-8','ignore')
                sample=text[:12000]
                delim=';' if sample.count(';')>sample.count(',') else ','
                reader=csv.DictReader(io.StringIO(text),delimiter=delim)
                for idx,rec in enumerate(reader):
                    if idx>600000:break
                    flat={str(k):clean(v) for k,v in rec.items()}; blobtxt=' | '.join(flat.values());matched=match_vendors_text(blobtxt,vendors)
                    if not matched:continue
                    buyer=extract_named_field(flat,['adjudicante','buyer','entidade'])
                    winner=extract_named_field(flat,['adjudicatario','cocontratante','fornecedor','winner'])
                    title=extract_named_field(flat,['objeto','descricao','description','title']) or 'Portal BASE / IMPIC public contract'
                    date=extract_named_field(flat,['data publicacao','data celebracao','date'])
                    for vendor in matched:
                        out.append({'title':title,'url':url,'snippet':clean(blobtxt[:2200]),'published':date,'engine':'dados-gov-pt','vendor':vendor,'country':'PT','procurement':True,'winner':winner,'buyer':buyer,'integrators':match_integrators_text(blobtxt)})
                        if len(out)>=2200:return out
    return out


# ----------------------------- Query planning -----------------------------

def previous_gap_priority() -> dict[str, int]:
    try:
        prev=json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return {x.get('vendor'): int(x.get('coverage',0)) for x in prev.get('coverage',[]) if x.get('vendor')}


def make_queries() -> list[dict]:
    fixed=[{"query":q,"kind":"strategic","country":"ALL","intent":"strategic","priority":100} for q in CFG.get("strategic_queries",[])]
    coverage=previous_gap_priority()
    generated=[]
    intents=CFG.get('deep_intents',{})
    countries={'ES':'Spain','PT':'Portugal'}
    vendors=tracked_names()
    for vendor in vendors:
        lowcov=100-coverage.get(vendor,45)
        aliases=aliases_for(vendor)
        # Search the most useful alias plus a secondary product/platform alias.
        vas=aliases[:2]
        for cc,country_word in countries.items():
            for intent,terms in intents.items():
                for term in terms[:8]:
                    alias=vas[(len(term)+len(vendor))%len(vas)]
                    generated.append({"query":f'"{alias}" {country_word} {term}',"kind":"vendor","vendor":vendor,"country":cc,"intent":intent,"priority":40+lowcov+(20 if intent in {'channel','ecosystem','customers','competition'} else 0)})
            # official-domain targeted search patterns for high-value proof
            domain=CFG.get('vendor_domains',{}).get(vendor)
            if domain and os.getenv('BRAVE_SEARCH_API_KEY','').strip():
                for term in ['partners','customer case study','press release','managed services','Spain','Portugal']:
                    generated.append({"query":f'site:{domain} "{vas[0]}" {country_word} {term}',"kind":"vendor","vendor":vendor,"country":cc,"intent":"official","priority":70+lowcov})
        # analyst/global strategic research
        for analyst in CFG.get('analyst_names',[]):
            generated.append({"query":f'"{vas[0]}" {analyst} 2026 public',"kind":"vendor","vendor":vendor,"country":"ALL","intent":"analyst","priority":52+lowcov})
    # Explicit distributor cross-checks: authoritative channel relationships are strategically critical.
    for vendor in active_vendor_names():
        for dist in CFG.get('known_distributors',[]):
            if dist in {'Westcon-Comstor','Comstor'}: continue
            generated.append({"query":f'"{vendor}" "{dist}" Spain distributor authorized linecard',"kind":"vendor","vendor":vendor,"country":"ES","intent":"channel","priority":90})
            generated.append({"query":f'"{vendor}" "{dist}" Portugal distributor authorized linecard',"kind":"vendor","vendor":vendor,"country":"PT","intent":"channel","priority":90})
        # Integrator cross-checks rotate deterministically so weekly runs eventually cover the whole ecosystem.
        ints=CFG.get('known_integrators',[])
        if ints:
            start=int(sha(str(NOW.isocalendar().week),vendor)[:6],16)%len(ints)
            selected=[ints[(start+i)%len(ints)] for i in range(min(8,len(ints)))]
            for integ in selected:
                generated.append({"query":f'"{vendor}" "{integ}" Spain partner case study',"kind":"vendor","vendor":vendor,"country":"ES","intent":"ecosystem","priority":76})
                generated.append({"query":f'"{vendor}" "{integ}" Portugal partner case study',"kind":"vendor","vendor":vendor,"country":"PT","intent":"ecosystem","priority":76})
    # Pairwise competitive intelligence: displacement, migration, TCO, integrators and customer proof.
    vi={x.get('name'):x for x in VENDOR_INTEL.get('vendors',[])}
    for vendor in active_vendor_names():
        for competitor in (vi.get(vendor,{}).get('marketCompetitors') or [])[:6]:
            generated.append({"query":f'"{vendor}" "{competitor}" Spain replacement migration TCO',"kind":"competitive-pair","vendor":vendor,"country":"ES","intent":"attack","priority":84})
            generated.append({"query":f'"{vendor}" "{competitor}" Portugal replacement migration TCO',"kind":"competitive-pair","vendor":vendor,"country":"PT","intent":"attack","priority":84})
            generated.append({"query":f'"{vendor}" "{competitor}" case study competitive win displacement',"kind":"competitive-pair","vendor":vendor,"country":"ALL","intent":"competition","priority":78})
    # Dedup then deterministic weighted rotation.
    ded={}
    for r in fixed+generated:
        ded[r['query']]=max(ded.get(r['query'],r),r,key=lambda x:x.get('priority',0)) if r['query'] in ded else r
    rows=list(ded.values())
    week=NOW.isocalendar().week
    rows.sort(key=lambda r:(-r.get('priority',0),sha(str(week),r['query'])))
    maxq=int(BUDGETS.get('query_limit_brave',BUDGETS.get('brave_queries_max',720)) if os.getenv('BRAVE_SEARCH_API_KEY','').strip() else BUDGETS.get('query_limit_no_brave',CFG.get('no_brave_rotation_max_queries',180)))
    return rows[:maxq]


# ----------------------------- Evidence normalisation -----------------------------

def to_evidence(x: dict, qrow: dict | None = None) -> dict:
    qrow=qrow or {}
    url=x.get('url') or ''
    tier=source_tier(url)
    vendor=x.get('vendor') or qrow.get('vendor')
    country=x.get('country') or qrow.get('country')
    scope=infer_scope(f"{x.get('title','')} {x.get('snippet','')} {qrow.get('query','')}",country)
    if country=='ES' and x.get('engine') in {'ted','placsp-open-data'}: scope='Spain'
    if country=='PT' and x.get('engine') in {'ted','dados-gov-pt'}: scope='Portugal'
    typ='procurement' if x.get('procurement') else infer_evidence_type(f"{x.get('title','')} {x.get('snippet','')} {qrow.get('query','')}",tier)
    direct=8 if x.get('engine') in {'ted','placsp-open-data','dados-gov-pt','official-sitemap'} else 0
    return {
        'id':sha(x.get('title'),url,vendor,country,x.get('engine'))[:16],
        'title':x.get('title') or 'Untitled public signal','url':url,'source':host(url) or x.get('engine'),'sourceTier':tier,
        'evidenceType':typ,'scope':scope,'kind':qrow.get('kind') or ('procurement' if x.get('procurement') else 'discovery'),
        'vendor':vendor,'country':country if country in {'ES','PT','IBERIA'} else None,'query':qrow.get('query'),'snippet':x.get('snippet'),
        'published':x.get('published'),'engine':x.get('engine'),'confidence':max(20,min(100,confidence_for(tier,scope,x.get('engine',''),direct)+freshness_bonus(x.get('published','')))),
        'collectedAt':NOW.isoformat(),'validationState':'primary/public source' if tier in {'regulator','public-open-data','official-company','analyst-public'} else 'discovery; validate before executive use',
        'buyer':x.get('buyer'),'winner':x.get('winner')
    }


def dedupe_evidence(evidence: list[dict]) -> list[dict]:
    bykey={}
    for e in evidence:
        key=sha(norm(e.get('url')),norm(e.get('title')),norm(e.get('vendor')),norm(e.get('country')))
        cur=bykey.get(key)
        if not cur or int(e.get('confidence',0))>int(cur.get('confidence',0)):
            bykey[key]=e
    return list(bykey.values())


def corroborate(evidence: list[dict]) -> list[dict]:
    # Raise confidence modestly when independent source domains corroborate same vendor/type/country theme.
    buckets=defaultdict(list)
    for e in evidence:
        k=(e.get('vendor'),e.get('evidenceType'),e.get('country') or e.get('scope'))
        if e.get('vendor'): buckets[k].append(e)
    for rows in buckets.values():
        domains={host(x.get('url','')) for x in rows if host(x.get('url',''))}
        bonus=min(8,max(0,len(domains)-1)*2)
        if bonus:
            for e in rows: e['confidence']=min(100,int(e.get('confidence',45))+bonus); e['corroboratedByDomains']=len(domains)
    return evidence


# ----------------------------- Relationship extraction -----------------------------

def countries_from_scope(scope: str) -> list[str]:
    out=[]
    if 'Spain' in scope or 'Iberia' in scope: out.append('ES')
    if 'Portugal' in scope or 'Iberia' in scope: out.append('PT')
    return out


def relation_candidates(evidence: list[dict]) -> list[dict]:
    distributors=CFG.get('known_distributors',[]); vendors=tracked_names(); rows={}
    for e in evidence:
        text=norm(f"{e.get('title','')} {e.get('snippet','')} {e.get('query','')}")
        matched_vendors=[v for v in vendors if any(norm(a) in text for a in aliases_for(v)[:3])]
        if e.get('vendor') and e['vendor'] not in matched_vendors: matched_vendors.append(e['vendor'])
        matched_dist=[d for d in distributors if norm(d) in text]
        if not matched_vendors or not matched_dist: continue
        countries=countries_from_scope(e.get('scope',''))
        if e.get('country') in {'ES','PT'} and e['country'] not in countries: countries.append(e['country'])
        for v in matched_vendors:
            for d in matched_dist:
                for cc in countries:
                    key=(v,cc,d); row=rows.setdefault(key,{'vendor':v,'country':cc,'distributor':d,'status':'candidate-public-signal','confidence':0,'evidence':[]})
                    row['confidence']=max(row['confidence'],min(96,int(e.get('confidence',45))+(6 if e.get('sourceTier') in {'official-company','public-open-data'} else 0)))
                    if e.get('id') not in row['evidence']: row['evidence'].append(e.get('id'))
    return sorted(rows.values(),key=lambda r:(-r['confidence'],r['vendor'],r['country'],r['distributor']))


def merge_channel_signals(*groups) -> list[dict]:
    merged={}
    for group in groups:
        for row in group:
            key=(row.get('vendor',''),row.get('country',''),row.get('distributor',''))
            if not all(key): continue
            cur=merged.get(key)
            if cur is None or int(row.get('confidence',0))>int(cur.get('confidence',0)): merged[key]=dict(row)
            else: cur['evidence']=list(dict.fromkeys((cur.get('evidence') or [])+(row.get('evidence') or [])))
    return sorted(merged.values(),key=lambda r:(-int(r.get('confidence',0)),r['vendor'],r['country'],r['distributor']))


def integrator_candidates(evidence: list[dict]) -> list[dict]:
    names=CFG.get('known_integrators',[]); vendors=tracked_names(); rows={}
    for e in evidence:
        text=norm(f"{e.get('title','')} {e.get('snippet','')} {e.get('query','')} {e.get('winner','')}")
        matched_vendors=[v for v in vendors if any(norm(a) in text for a in aliases_for(v)[:3])]
        if e.get('vendor') and e['vendor'] not in matched_vendors: matched_vendors.append(e['vendor'])
        matched=[n for n in names if norm(n) in text]
        if e.get('winner') and e['winner'] and e['winner'] not in matched: matched.append(e['winner'])
        if not matched_vendors or not matched: continue
        if e.get('evidenceType') not in {'integrator','customer','partner-program','services','procurement'} and not any(x in text for x in ['partner','integrator','mssp','implementation','winner','adjudicat']): continue
        countries=countries_from_scope(e.get('scope','')) or ([e['country']] if e.get('country') in {'ES','PT'} else [])
        for cc in countries:
            for v in matched_vendors:
                for name in matched[:4]:
                    if not clean(name): continue
                    key=(v,cc,clean(name)); row=rows.setdefault(key,{'vendor':v,'country':cc,'name':clean(name),'role':'Integrador / Partner','status':'candidate-public-signal','confidence':0,'evidence':[],'url':e.get('url')})
                    bonus=10 if e.get('sourceTier') in {'official-company','public-open-data'} else 0
                    row['confidence']=max(row['confidence'],min(96,int(e.get('confidence',45))+bonus))
                    if e.get('id') not in row['evidence']: row['evidence'].append(e.get('id'))
    return sorted(rows.values(),key=lambda r:(-int(r.get('confidence',0)),r['vendor'],r['country'],r['name']))


def merge_integrators(*groups) -> list[dict]:
    merged={}
    for group in groups:
        for row in group:
            key=(row.get('vendor',''),row.get('country',''),norm(row.get('name','')))
            if not all(key): continue
            cur=merged.get(key)
            if cur is None or int(row.get('confidence',0))>int(cur.get('confidence',0)): merged[key]=dict(row)
            else: cur['evidence']=list(dict.fromkeys((cur.get('evidence') or [])+(row.get('evidence') or [])))
    return sorted(merged.values(),key=lambda r:(-int(r.get('confidence',0)),r['vendor'],r['country'],r['name']))


def procurement_customer_candidates(evidence: list[dict]) -> list[dict]:
    rows={}
    for e in evidence:
        if e.get('evidenceType')!='procurement' or not e.get('vendor') or not e.get('buyer'): continue
        cc=e.get('country') or ('ES' if 'Spain' in e.get('scope','') else 'PT' if 'Portugal' in e.get('scope','') else '')
        if cc not in {'ES','PT'}: continue
        buyer=clean(e['buyer']);
        if not buyer: continue
        key=(e['vendor'],cc,norm(buyer)); rows[key]={'vendor':e['vendor'],'country':cc,'name':buyer,'sector':'Sector público','solution':'Señal de contratación pública relacionada con la tecnología/vendor','date':e.get('published') or TODAY,'confidence':min(92,int(e.get('confidence',80))),'source':e.get('source'),'url':e.get('url'),'proofType':'public-procurement','evidence':[e.get('id')]}
    return list(rows.values())


def merge_customers(*groups) -> list[dict]:
    merged={}
    for group in groups:
        for row in group:
            key=(row.get('vendor',''),row.get('country',''),norm(row.get('name','')))
            if not all(key): continue
            cur=merged.get(key)
            if cur is None or int(row.get('confidence',0))>int(cur.get('confidence',0)): merged[key]=dict(row)
            else: cur['evidence']=list(dict.fromkeys((cur.get('evidence') or [])+(row.get('evidence') or [])))
    return sorted(merged.values(),key=lambda r:(-int(r.get('confidence',0)),r['vendor'],r['country'],r['name']))


def analyst_candidates(evidence: list[dict]) -> list[dict]:
    names=CFG.get('analyst_names',[]); out=[]
    for e in evidence:
        txt=f"{e.get('title','')} {e.get('snippet','')}"; analyst=next((a for a in names if norm(a) in norm(txt) or norm(a) in norm(e.get('source'))),None)
        if not analyst and e.get('sourceTier')!='analyst-public': continue
        stats=re.findall(r"(?:\$|€)?\s?\d+(?:[.,]\d+)?\s?(?:trillion|billion|million|tn|bn|m|%)",txt,flags=re.I)
        out.append({'evidenceId':e['id'],'analyst':analyst or e.get('source','Analyst'),'vendor':e.get('vendor'),'scope':e.get('scope'),'title':e.get('title'),'candidateStats':stats[:6],'confidence':e.get('confidence',45),'status':'public-summary' if e.get('sourceTier')=='analyst-public' else 'discovery-only','evidenceType':e.get('evidenceType','analyst')})
    return out


def vendor_coverage(evidence, channel_rows, integrator_rows, customer_rows) -> list[dict]:
    vendors=active_vendor_names(); result=[]
    for vendor in vendors:
        rows=[e for e in evidence if e.get('vendor')==vendor or any(norm(a) in norm(f"{e.get('title','')} {e.get('snippet','')} {' '.join(map(str,e.get('tags',[])))}") for a in aliases_for(vendor)[:3])]
        kinds={e.get('evidenceType') or e.get('kind') for e in rows}; analysts={e.get('source') for e in rows if e.get('sourceTier')=='analyst-public'}; official={e.get('source') for e in rows if e.get('sourceTier') in {'official-company','regulator','public-open-data'}}
        channel=[c for c in channel_rows if c.get('vendor')==vendor and c.get('distributor') not in {'Westcon-Comstor','Comstor'}]; ints=[x for x in integrator_rows if x.get('vendor')==vendor]; cust=[x for x in customer_rows if x.get('vendor')==vendor]
        dimensions={'channelES':any(c.get('country') in {'ES','IBERIA'} for c in channel),'channelPT':any(c.get('country') in {'PT','IBERIA'} for c in channel),'integratorES':any(x.get('country') in {'ES','IBERIA'} for x in ints),'integratorPT':any(x.get('country') in {'PT','IBERIA'} for x in ints),'customerES':any(x.get('country') in {'ES','IBERIA'} for x in cust),'customerPT':any(x.get('country') in {'PT','IBERIA'} for x in cust),'procurement':any(e.get('evidenceType')=='procurement' for e in rows),'analyst':bool(analysts),'market':'market' in kinds,'competitive':'competitive' in kinds,'ma':'m&a' in kinds,'product':'product' in kinds,'services':'services' in kinds or 'partner-program' in kinds,'official':bool(official)}
        score=round(sum(bool(x) for x in dimensions.values())/len(dimensions)*100)
        result.append({'vendor':vendor,'coverage':score,'dimensions':dimensions,'evidenceCount':len(rows),'analystSources':sorted(x for x in analysts if x),'officialSources':sorted(x for x in official if x),'alternativeChannelSignals':len(channel),'integratorSignals':len(ints),'customerSignals':len(cust),'procurementSignals':sum(1 for e in rows if e.get('evidenceType')=='procurement'),'customerSectors':sorted({x.get('sector') for x in cust if x.get('sector')})})
    return sorted(result,key=lambda x:(x['coverage'],x['vendor']))


def research_gaps(coverage) -> list[dict]:
    labels={'channelES':'mayoristas alternativos en España','channelPT':'mayoristas alternativos en Portugal','integratorES':'integradores demostrados en España','integratorPT':'integradores demostrados en Portugal','customerES':'referencias públicas de cliente en España','customerPT':'referencias públicas de cliente en Portugal','procurement':'contratación pública ES/PT','analyst':'señal pública de analistas','market':'tamaño/crecimiento de mercado','competitive':'evidencia competitiva/displacement','ma':'M&A/cambio estratégico','product':'novedades de plataforma/producto','services':'servicios/programa de canal','official':'fuente oficial directa'}
    out=[]
    for row in coverage:
        missing=[labels[k] for k,v in row['dimensions'].items() if not v]
        if missing: out.append({'vendor':row['vendor'],'coverage':row['coverage'],'missing':missing,'priority':'P0' if row['coverage']<35 else 'P1' if row['coverage']<60 else 'P2'})
    return out


def signal_stats(evidence) -> dict:
    by_tier=Counter(); by_type=Counter(); by_scope=Counter(); by_source=Counter(); by_engine=Counter()
    for e in evidence:
        by_tier[e.get('sourceTier','unknown')]+=1; by_type[e.get('evidenceType') or e.get('kind') or 'general']+=1; by_scope[e.get('scope') or 'unknown']+=1; by_source[e.get('source') or 'unknown']+=1; by_engine[e.get('engine') or 'curated']+=1
    return {'byTier':dict(by_tier),'byType':dict(by_type),'byScope':dict(by_scope),'byEngine':dict(by_engine),'topSources':by_source.most_common(30)}


# ----------------------------- Main -----------------------------

def competitive_attack_matrix(evidence: list[dict], channels: list[dict], integrators: list[dict], customers: list[dict]) -> list[dict]:
    vi={x.get('name'):x for x in VENDOR_INTEL.get('vendors',[])}
    initiatives=DEEP.get('westcon_initiatives',[])
    rows=[]
    for vendor in active_vendor_names():
        competitors=(vi.get(vendor,{}).get('marketCompetitors') or [])[:8]
        vints={norm(x.get('name')) for x in integrators if x.get('vendor')==vendor}
        vcust={norm(x.get('name')) for x in customers if x.get('vendor')==vendor}
        vchan={(x.get('country'),norm(x.get('distributor'))) for x in channels if x.get('vendor')==vendor}
        for comp in competitors:
            ce=[e for e in evidence if e.get('vendor')==vendor and e.get('kind')=='competitive-pair' and norm(comp) in norm(f"{e.get('title','')} {e.get('snippet','')} {e.get('query','')}")]
            cint={norm(x.get('name')) for x in integrators if norm(x.get('vendor'))==norm(comp)}
            ccust={norm(x.get('name')) for x in customers if norm(x.get('vendor'))==norm(comp)}
            shared_i=len(vints & cint); shared_c=len(vcust & ccust)
            proof=min(100,18+len(ce)*9+sum(1 for e in ce if e.get('sourceTier') in {'official-company','analyst-public','public-open-data'})*11)
            whitespace=max(10,min(100,70-shared_i*7-shared_c*6+(18 if not ce else 0)))
            # Pick initiatives based on likely gaps rather than generic ranking.
            chosen=[]
            wanted=['3d-labs','assessments','services','flex','intelligent-demand','tech-xpert','lifecycle','gscs']
            if shared_i: wanted=['blueprint','tech-xpert','3d-labs','intelligent-demand','services','flex']
            if shared_c: wanted=['assessments','3d-labs','services','lifecycle','flex','intelligent-demand']
            for iid in wanted:
                item=next((x for x in initiatives if x.get('id')==iid),None)
                if item: chosen.append(item.get('name'))
            rows.append({'vendor':vendor,'competitor':comp,'evidenceCount':len(ce),'proofStrength':proof,'sharedIntegrators':shared_i,'sharedCustomers':shared_c,'whiteSpace':whitespace,'recommendedInitiatives':chosen[:5],'evidenceIds':[e.get('id') for e in sorted(ce,key=lambda x:-int(x.get('confidence',0)))[:8]],'attackHypothesis':f"Desplazar/contener {comp} usando prueba técnica, servicios y ecosistema; priorizar gaps con evidencia y validar por país antes de ejecutar."})
    return sorted(rows,key=lambda x:(x['vendor'],-x['proofStrength'],-x['whiteSpace'],x['competitor']))

def main() -> None:
    brave=bool(os.getenv('BRAVE_SEARCH_API_KEY','').strip())
    prev=load_previous_payload()
    queries=make_queries()
    evidence=[dict(e,curated=True) for e in CURATED.get('evidence',[])]
    evidence.extend(carryover_evidence(prev))

    # 1) Broad discovery engines with profile-specific budgets.
    news_budget=int(BUDGETS.get('news_queries_max',180)); gdelt_budget=int(BUDGETS.get('gdelt_queries_max',150)); arquivo_budget=int(BUDGETS.get('arquivo_queries_max',40))
    news_n=gdelt_n=arquivo_n=0; tasks=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for qrow in queries:
            if brave: tasks.append((qrow,'brave',ex.submit(search_brave,qrow)))
            if news_n<news_budget and ((not brave) or qrow.get('kind')=='strategic' or qrow.get('intent') in {'channel','channel_changes','competition','attack','customers','customer_verticals','analyst','analysts'}):
                tasks.append((qrow,'news',ex.submit(search_google_news,qrow))); news_n+=1
            if gdelt_n<gdelt_budget and (qrow.get('intent') in {'channel','channel_changes','ecosystem','partner_capability','customers','customer_verticals','competition','attack','strategy','services'} or qrow.get('kind')=='strategic'):
                tasks.append((qrow,'gdelt',ex.submit(search_gdelt,qrow))); gdelt_n+=1
            if arquivo_n<arquivo_budget and qrow.get('country')=='PT' and qrow.get('intent') in {'channel','channel_changes','ecosystem','partner_capability','customers','customer_verticals'}:
                tasks.append((qrow,'arquivo',ex.submit(search_arquivo,qrow))); arquivo_n+=1
        for qrow,engine,fut in tasks:
            try: rows=fut.result()
            except Exception as exc:
                print(f"{engine} error {qrow.get('query')!r}: {exc}"); continue
            for x in rows: evidence.append(to_evidence(x,qrow))

    # 2) Primary-source crawling: vendor, distributor, integrator and analyst public pages.
    try:
        for x in official_sitemap_evidence(active_vendor_names()+[v.get('name') for v in BASE.get('externalCompetitors',[]) if v.get('name')]):
            evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-vendor-crawl','country':x.get('country'),'query':'official vendor sitemap crawl'}))
    except Exception as exc: print('vendor sitemap crawl error:',exc)
    try:
        budget=int(BUDGETS.get('ecosystem_sitemap_pages_max',0))
        dist_budget=budget//2; int_budget=budget-dist_budget
        for x in official_entity_sitemap_evidence(CFG.get('distributor_domains',{}),'distributor',dist_budget):
            evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-distributor-crawl','country':x.get('country'),'query':f"official distributor crawl {x.get('sourceEntity','')}"}))
        for x in official_entity_sitemap_evidence(CFG.get('integrator_domains',{}),'integrator',int_budget):
            evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-integrator-crawl','country':x.get('country'),'query':f"official integrator crawl {x.get('sourceEntity','')}"}))
    except Exception as exc: print('ecosystem sitemap crawl error:',exc)
    if PROFILE=='deep':
        try:
            for x in official_analyst_sitemap_evidence(int(BUDGETS.get('analyst_sitemap_pages_max',0))):
                evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'analyst-official-crawl','country':'ALL','query':'public analyst sitemap crawl'}))
        except Exception as exc: print('analyst sitemap crawl error:',exc)

    # 3) Public procurement. Daily prioritises low-coverage vendors; deep traverses the whole active portfolio.
    procurement=[]
    cov=previous_gap_priority(); ranked=sorted(active_vendor_names(),key=lambda v:(cov.get(v,0),v))
    ted_limit=int(BUDGETS.get('ted_vendor_limit',len(ranked))); ted_vendors=ranked[:ted_limit]
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(ted_search,v,c):(v,c) for v in ted_vendors for c in ('ES','PT')}
        for fut in as_completed(futs):
            try: procurement.extend(fut.result())
            except Exception: pass
    if BUDGETS.get('full_procurement',False):
        try: procurement.extend(official_spain_procurement_rows(active_vendor_names()))
        except Exception as exc: print('PLACSP error:',exc)
        try: procurement.extend(dados_gov_pt_contract_rows(active_vendor_names()))
        except Exception as exc: print('dados.gov.pt error:',exc)
    for x in procurement: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'procurement','country':x.get('country'),'query':'public procurement'}))

    # 4) Deduplication, accumulation and corroboration.
    evidence=corroborate(dedupe_evidence(evidence))

    # 5) Relationship graph and coverage.
    channels=merge_channel_signals(CURATED.get('channelSignals',[]),relation_candidates(evidence))
    seeded_integrators=[dict(x,status='curated-public') for x in ECOSYSTEM.get('integrators',[]) if x.get('vendor')!='Juniper Networks']
    integrators=merge_integrators(seeded_integrators,integrator_candidates(evidence))
    seeded_customers=[dict(x,status='curated-public') for x in ECOSYSTEM.get('customers',[]) if x.get('vendor')!='Juniper Networks']
    customers=merge_customers(seeded_customers,procurement_customer_candidates(evidence))
    analysts=analyst_candidates(evidence)
    coverage=vendor_coverage(evidence,channels,integrators,customers)
    conflicts=detect_conflicts(evidence,channels)
    attack_matrix=competitive_attack_matrix(evidence,channels,integrators,customers)
    changes=compute_changes(prev,channels,integrators,customers,coverage)

    payload={
        'generatedAt':NOW.isoformat(),'profile':PROFILE,'mode':'deep-public-research-v4.2','queryCount':len(queries),'braveEnabled':brave,
        'notice':'Solo inteligencia pública externa. Discovery, evidencia ejecutiva, geografía, frescura, corroboración y conflictos se preservan explícitamente. El scope de portfolio se configura aparte del motor de evidencia.',
        'researchEngines':['Brave Search (optional)' if brave else 'Brave Search (not configured)','Google News RSS','GDELT DOC 2.0','Arquivo.pt','official vendor sitemaps','official distributor/integrator sitemaps','public analyst sitemaps' if PROFILE=='deep' else 'public analyst crawl (weekly)','TED Search API','PLACSP open data (weekly deep)','dados.gov.pt / Portal BASE (weekly deep)'],
        'evidence':evidence,'channelSignals':channels,'integratorSignals':integrators,'customerSignals':customers,'analystSignals':analysts,'coverage':coverage,'gaps':research_gaps(coverage),'conflicts':conflicts,'competitiveAttackMatrix':attack_matrix,'changes':changes,
        'derived':{'evidenceCount':len(evidence),'officialOrAnalystCount':sum(1 for e in evidence if e.get('sourceTier') in {'official-company','regulator','public-open-data','analyst-public'}),'channelSignalCount':len(channels),'integratorSignalCount':len(integrators),'customerSignalCount':len(customers),'procurementSignalCount':sum(1 for e in evidence if e.get('evidenceType')=='procurement'),'analystSignalCount':len(analysts),'conflictCount':len(conflicts),'competitiveAttackRows':len(attack_matrix),'changeCount':len(changes),'statistics':signal_stats(evidence)}
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    CHANGES_OUT.write_text(json.dumps({'generatedAt':NOW.isoformat(),'profile':PROFILE,'changes':changes,'conflicts':conflicts},ensure_ascii=False,indent=2),encoding='utf-8')
    STATUS_OUT.write_text(json.dumps({'generatedAt':NOW.isoformat(),'profile':PROFILE,'braveEnabled':brave,'queryCount':len(queries),'budgets':BUDGETS,'coverageAverage':round(sum(x['coverage'] for x in coverage)/max(1,len(coverage)),1),'vendorsWithCoverage70':sum(1 for x in coverage if x['coverage']>=70),'gapsP0':sum(1 for x in research_gaps(coverage) if x['priority']=='P0'),'engines':payload['researchEngines']},ensure_ascii=False,indent=2),encoding='utf-8')
    write_light_history(payload,changes)
    print(f"Research v4.2/{PROFILE}: {len(evidence)} evidence, {len(channels)} channel, {len(integrators)} integrators, {len(customers)} customers, {len(queries)} planned queries, {len(changes)} changes")


if __name__=='__main__': main()
