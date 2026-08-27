#!/usr/bin/env python3
"""Bounded, adaptive and observable public-intelligence collector v3.0.

Design goals
------------
* Public external information only.
* Preserve geography (ES/PT/Iberia/EMEA/global) and confidence.
* Separate discovery from executive-grade evidence.
* Search broadly, then de-duplicate and corroborate.
* Use only no-key public sources (TED, GDELT, Arquivo.pt, official sitemaps,
  Spanish procurement open data and dados.gov.pt).
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
import gzip
import json
import os
import pathlib
import random
import re
import signal
import subprocess
import time
import threading
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except (ImportError, ModuleNotFoundError):  # offline self-test shim
    HTTPAdapter = Retry = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "data/base.json").read_text(encoding="utf-8"))
CFG = json.loads((ROOT / "config/research_queries.json").read_text(encoding="utf-8"))
REG = json.loads((ROOT / "config/source_registry.json").read_text(encoding="utf-8"))
DEEP = json.loads((ROOT / "config/deep_research.json").read_text(encoding="utf-8"))
UNIVERSE_PATH = ROOT / "config/source_universe.json"
UNIVERSE = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8")) if UNIVERSE_PATH.exists() else {}
V36_PORTAL_PATH = ROOT / "config/v36/vendor_portal_intelligence.json"
V36_PORTALS = json.loads(V36_PORTAL_PATH.read_text(encoding="utf-8")) if V36_PORTAL_PATH.exists() else {"seeds": []}
CURATED = json.loads((ROOT / "data/curated_evidence.json").read_text(encoding="utf-8"))
ECOSYSTEM = json.loads((ROOT / "data/ecosystem.json").read_text(encoding="utf-8"))
VENDOR_INTEL = json.loads((ROOT / "data/vendor_intelligence.json").read_text(encoding="utf-8"))
PROC_TAX = json.loads((ROOT / "config/procurement_taxonomy.json").read_text(encoding="utf-8"))
CAP = json.loads((ROOT / "config/capability_intelligence.json").read_text(encoding="utf-8"))
MARKET_REALITY = json.loads((ROOT / "data/market_reality.json").read_text(encoding="utf-8"))
OUT = ROOT / "data/research.latest.json"
STATUS_OUT = ROOT / "data/research_status.json"
CHANGES_OUT = ROOT / "data/changes.latest.json"
LEARNING_OUT = ROOT / "data/research_learning.json"
QUEUE_OUT = ROOT / "data/research_queue.json"
SOURCE_HEALTH_OUT = ROOT / "data/source_health.json"
ERRORS_OUT = ROOT / "data/research_errors.json"
RUN_MANIFEST_OUT = ROOT / "data/run_manifest.latest.json"
DYNAMIC_ENTITIES_OUT = ROOT / "data/discovered_entities.json"
HISTORY = ROOT / "data/history"
HISTORY.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
RUN_ID = f"{NOW.strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
PROFILE = os.getenv("RESEARCH_PROFILE", "deep").strip().lower()
for _arg in os.sys.argv[1:]:
    if _arg.startswith("--profile="):
        PROFILE = _arg.split("=", 1)[1].strip().lower()
if PROFILE not in DEEP.get("profiles", {}):
    PROFILE = "deep"
PROFILE_CFG = DEEP.get("profiles", {}).get(PROFILE, {})
BUDGETS = dict(DEEP.get("budgets", {}))
BUDGETS.update(PROFILE_CFG.get("budgets", {}))
for _kind, _key, _domain_key in (("distributors", "known_distributors", "distributor_domains"), ("integrators", "known_integrators", "integrator_domains"), ("analysts", "analyst_names", "analyst_domains")):
    _rows = UNIVERSE.get(_kind, [])
    CFG[_key] = list(dict.fromkeys([*CFG.get(_key, []), *[x.get("name") for x in _rows if x.get("name")]]))
    CFG[_domain_key] = {**{x.get("name"): x.get("domain") for x in _rows if x.get("name") and x.get("domain")}, **CFG.get(_domain_key, {})}

_max_runtime_arg = next((x.split("=", 1)[1] for x in os.sys.argv[1:] if x.startswith("--max-runtime=")), "")
MAX_RUNTIME_SECONDS = max(30, int(_max_runtime_arg or os.getenv("RESEARCH_MAX_RUNTIME_SECONDS") or PROFILE_CFG.get("max_runtime_seconds", 2100)))
RUN_STARTED = time.monotonic()
DEADLINE = RUN_STARTED + MAX_RUNTIME_SECONDS
STOP_REQUESTED = False
STOP_REASON = ""
UA = f"Westcon-Iberia-Decision-Intelligence/3.0 ({PROFILE}; bounded-adaptive-public-intelligence)"
TIMEOUT = int(BUDGETS.get("request_timeout_seconds", 25))
WORKERS = int(BUDGETS.get("http_workers", 12))

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9,pt;q=0.8,en;q=0.7"})
_resilience = DEEP.get("resilience", {})
if Retry and HTTPAdapter and hasattr(SESSION, "mount"):
    _retry = Retry(total=int(_resilience.get("http_retry_total", 4)), connect=3, read=3,
                   backoff_factor=float(_resilience.get("http_backoff_factor", .8)),
                   status_forcelist=_resilience.get("retry_statuses", [429, 500, 502, 503, 504]),
                   allowed_methods=frozenset(["GET", "POST"]), respect_retry_after_header=True)
    SESSION.mount("https://", HTTPAdapter(max_retries=_retry, pool_connections=WORKERS * 2, pool_maxsize=WORKERS * 2))
SITEMAP_CACHE: dict[str, list[str]] = {}
PAGE_CACHE: dict[str, dict | None] = {}
SOURCE_HEALTH = {"version": 1, "sources": {}}
SOURCE_HEALTH_LOCK = threading.Lock()
RUN_STAGES: list[dict] = []
RUN_ERRORS: list[dict] = []


def _request_stop(signum=None, frame=None) -> None:
    """Ask every bounded stage to finish and publish what it already has."""
    global STOP_REQUESTED, STOP_REASON
    STOP_REQUESTED = True
    STOP_REASON = f"signal-{signum}" if signum else "requested"


signal.signal(signal.SIGINT, _request_stop)
signal.signal(signal.SIGTERM, _request_stop)


def seconds_left() -> float:
    return max(0.0, DEADLINE - time.monotonic())


def should_stop(reserve_seconds: int = 90) -> bool:
    return STOP_REQUESTED or seconds_left() <= reserve_seconds


def bounded_timeout(preferred: int | float | None = None, floor: int = 3) -> int:
    """Never let one request consume the remaining publication window."""
    desired = int(preferred or TIMEOUT)
    return max(floor, min(desired, int(max(floor, seconds_left() - 75))))


def rotate_rows(rows, limit: int, salt: str):
    """Cover a large universe over successive runs without an all-or-nothing crawl."""
    values = list(rows)
    if limit <= 0 or len(values) <= limit:
        return values
    seed = int(sha(PROFILE, str(NOW.isocalendar().week), salt)[:10], 16)
    start = seed % len(values)
    ring = values[start:] + values[:start]
    return ring[:limit]


def clamp(value, minimum: int = 0, maximum: int = 100) -> int:
    """Clamp a numeric score to an inclusive range, mirroring the UI helper.

    Kept in the research engine because aggregate functions run server-side in
    GitHub Actions and must not depend on JavaScript utilities.
    """
    try:
        number = round(float(value or 0))
    except (TypeError, ValueError):
        number = 0
    return max(minimum, min(maximum, number))


def clean(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def trace_error(stage: str, exc, source: str = "", recoverable: bool = True) -> None:
    row = {
        "runId": RUN_ID,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "profile": PROFILE,
        "stage": stage,
        "source": source,
        "errorType": type(exc).__name__,
        "message": clean(str(exc))[:700],
        "recoverable": bool(recoverable)
    }
    RUN_ERRORS.append(row)
    print(f"[{stage}] {row['errorType']}: {row['message']}", flush=True)


def stage_start(name: str) -> tuple[dict, float]:
    row = {"name": name, "status": "running", "startedAt": dt.datetime.now(dt.timezone.utc).isoformat()}
    RUN_STAGES.append(row)
    print(f"stage {name} started · {seconds_left():.0f}s left", flush=True)
    return row, time.monotonic()


def stage_end(row: dict, started: float, status: str = "completed", **metrics) -> None:
    row.update({"status": status, "durationSeconds": round(time.monotonic()-started, 2), "finishedAt": dt.datetime.now(dt.timezone.utc).isoformat(), **metrics})
    print(f"stage {row['name']} {status} · {row['durationSeconds']}s · {seconds_left():.0f}s left", flush=True)


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
    official_domains = set(CFG.get("vendor_domains", {}).values()) | set(CFG.get("distributor_domains", {}).values()) | set(CFG.get("integrator_domains", {}).values())
    analyst_domains = set(CFG.get("analyst_domains", {}).values())
    institutional_domains = {x.get('domain'): x.get('type','') for x in UNIVERSE.get('institutionalSources',[]) if x.get('domain')}
    if any(h == d or h.endswith("." + d) for d in official_domains if d):
        return "official-company"
    if any(h == d or h.endswith("." + d) for d in analyst_domains if d):
        return "analyst-public"
    for d,kind in institutional_domains.items():
        if h == d or h.endswith('.'+d):
            return 'public-open-data' if 'procurement' in kind or 'statistics' in kind else 'regulator'
    return "search-discovery"


def tier_weight(tier: str) -> int:
    for row in REG.get("tiers", []):
        if row.get("id") == tier:
            return int(row.get("weight", 50))
    return 45


def sha(*parts: str) -> str:
    return hashlib.sha1("|".join(str(x or "") for x in parts).encode("utf-8", "ignore")).hexdigest()


def atomic_json(path: pathlib.Path, payload: dict) -> None:
    """Never leave a half-written state if a run is interrupted."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_run_diagnostics(outcome: str, **extra) -> None:
    previous = load_json_state(ERRORS_OUT, {"errors": []}).get("errors", [])
    errors = (previous + RUN_ERRORS)[-300:]
    atomic_json(ERRORS_OUT, {"version": 2, "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "lastRunId": RUN_ID, "errors": errors})
    atomic_json(SOURCE_HEALTH_OUT, {**SOURCE_HEALTH, "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "runId": RUN_ID})
    atomic_json(RUN_MANIFEST_OUT, {
        "version": 2, "runId": RUN_ID, "profile": PROFILE, "startedAt": NOW.isoformat(),
        "finishedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "outcome": outcome,
        "maxRuntimeSeconds": MAX_RUNTIME_SECONDS, "elapsedSeconds": round(time.monotonic()-RUN_STARTED, 2),
        "stopReason": STOP_REASON or ("deadline" if should_stop(0) else ""), "stages": RUN_STAGES,
        "errorCount": len(RUN_ERRORS), "errorsFile": "data/research_errors.json", **extra
    })


def load_json_state(path: pathlib.Path, default: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except Exception:
        return default


SOURCE_HEALTH = load_json_state(SOURCE_HEALTH_OUT, {"version": 1, "sources": {}})


def record_source_health(url: str, ok: bool, latency: float, yielded: int = 0, error: str = "") -> None:
    """Learn availability, latency and useful yield without letting telemetry break research."""
    h = host(url)
    if not h:
        return
    try:
        with SOURCE_HEALTH_LOCK:
            row = SOURCE_HEALTH.setdefault("sources", {}).setdefault(h, {"attempts": 0, "successes": 0, "failures": 0, "usefulHits": 0, "latencyMsEma": 0})
            row["attempts"] = int(row.get("attempts", 0)) + 1
            row["successes" if ok else "failures"] = int(row.get("successes" if ok else "failures", 0)) + 1
            row["usefulHits"] = int(row.get("usefulHits", 0)) + int(max(0, yielded))
            ms = max(0, round(latency * 1000))
            row["latencyMsEma"] = round(ms if not row.get("latencyMsEma") else float(row["latencyMsEma"]) * .78 + ms * .22)
            row["successRate"] = round(int(row.get("successes", 0)) / max(1, int(row.get("attempts", 0))), 4)
            row["lastAttemptAt"] = NOW.isoformat()
            if ok:
                row["lastSuccessAt"] = NOW.isoformat()
                row["consecutiveFailures"] = 0
                row.pop("cooldownUntil", None)
                row.pop("lastError", None)
            else:
                row["consecutiveFailures"] = int(row.get("consecutiveFailures", 0)) + 1
                row["lastError"] = clean(error)[:240]
                if row["consecutiveFailures"] >= 3:
                    minutes = min(1440, 15 * (2 ** min(6, row["consecutiveFailures"] - 3)))
                    row["cooldownUntil"] = (NOW + dt.timedelta(minutes=minutes)).isoformat()
    except Exception:
        pass


def source_in_cooldown(domain: str) -> bool:
    value=SOURCE_HEALTH.get('sources',{}).get(domain,{}).get('cooldownUntil')
    if not value: return False
    try: return dt.datetime.fromisoformat(value.replace('Z','+00:00'))>NOW
    except Exception: return False


def source_priority(domain: str) -> float:
    """Balance useful yield, reliability, speed, freshness and exploration."""
    row=SOURCE_HEALTH.get('sources',{}).get(domain,{})
    attempts=max(0,int(row.get('attempts',0)));success=float(row.get('successRate',0.5 if not attempts else 0));hits=int(row.get('usefulHits',0));latency=float(row.get('latencyMsEma',2500));
    exploration=(2.0/(attempts+1))**.5
    stale=1.0
    try:
        last=dt.datetime.fromisoformat(str(row.get('lastSuccessAt','')).replace('Z','+00:00'));stale=min(2.2,max(.3,(NOW-last).days/45))
    except Exception: pass
    return success*3.2+min(2.4,(hits+1)**.35)+exploration*1.8+stale-latency/12000-(4 if source_in_cooldown(domain) else 0)


def adaptive_source_selection(items, limit: int, salt: str, domain_of):
    values=list(items)
    if limit<=0 or len(values)<=limit: return values
    exploit=max(1,round(limit*.72));ranked=sorted(values,key=lambda x:(-source_priority(domain_of(x)),str(x)))
    selected=ranked[:exploit];remaining=[x for x in values if x not in selected and not source_in_cooldown(domain_of(x))]
    selected.extend(rotate_rows(remaining,limit-len(selected),salt+'-explore'))
    if len(selected)<limit: selected.extend(x for x in ranked if x not in selected)
    return selected[:limit]


def learning_key(row: dict, engine: str = "all") -> str:
    return "|".join([engine, row.get("kind", "other"), row.get("intent", "other"), row.get("country", "ALL")])


def adaptive_bonus(row: dict, learning: dict) -> int:
    suffix="|".join([row.get("kind", "other"), row.get("intent", "other"), row.get("country", "ALL")])
    matches=[v for k,v in learning.get("strategies", {}).items() if k.endswith(suffix)]
    trials = max(1, sum(int(x.get("trials",0)) for x in matches))
    mean = sum(float(x.get("reward",0)) for x in matches) / trials
    explore = (2 * max(1, int(learning.get("totalTrials", 1))) ** .5 / trials) ** .5
    return round(min(float(DEEP.get("adaptive_learning", {}).get("priority_boost_max", 35)), (mean + explore) * 18))


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
    if engine == "google-news-rss" and tier == "search-discovery":
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
        ("analyst", ["gartner", "forrester", "idc", "omdia", "canalys", "dell oro", "synergy research", "kuppingercole", "everest group", "gigaom", "magic quadrant", "wave", "marketscape", "peak matrix", "leadership compass", "radar"]),
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


def robots_sitemaps(domain: str) -> list[str]:
    out=[]
    for base in [f'https://{domain}',f'https://www.{domain}']:
        if should_stop(120): break
        started=time.monotonic()
        try:
            r=SESSION.get(base+'/robots.txt',timeout=bounded_timeout(min(TIMEOUT,10)))
            if r.status_code<400:
                out.extend(re.findall(r'^\s*Sitemap:\s*(\S+)',r.text,flags=re.I|re.M))
            record_source_health(base, r.status_code < 400, time.monotonic()-started, len(out))
        except Exception as exc:
            record_source_health(base, False, time.monotonic()-started, error=str(exc))
    return list(dict.fromkeys(out))[:30]


def _sitemap_text(resp: requests.Response, url: str) -> str:
    content=resp.content
    if url.lower().endswith('.gz') or resp.headers.get('content-type','').lower().find('gzip')>=0 or content[:2]==b'\x1f\x8b':
        try: content=gzip.decompress(content)
        except Exception: pass
    for enc in ('utf-8','utf-8-sig','latin-1'):
        try: return content.decode(enc)
        except Exception: continue
    return ''


def discover_sitemap_urls(domain: str, max_urls: int = 120) -> list[str]:
    cache_key=f'{domain}|{max_urls}'
    if cache_key in SITEMAP_CACHE: return SITEMAP_CACHE[cache_key]
    if source_in_cooldown(domain): return []
    seeds=[f"https://{domain}/sitemap.xml",f"https://www.{domain}/sitemap.xml",f"https://{domain}/sitemap_index.xml",*robots_sitemaps(domain)]
    seen_maps, urls=set(),[]; queue=list(dict.fromkeys(seeds))
    while queue and len(urls)<max_urls*5 and not should_stop(120):
        sm=queue.pop(0)
        if sm in seen_maps: continue
        seen_maps.add(sm)
        started=time.monotonic()
        try:
            r=SESSION.get(sm,timeout=bounded_timeout()); r.raise_for_status(); us,ms=parse_sitemap(_sitemap_text(r,sm))
            record_source_health(sm, True, time.monotonic()-started, len(us))
        except Exception as exc:
            record_source_health(sm, False, time.monotonic()-started, error=str(exc))
            continue
        urls.extend(us); queue.extend(ms[:40])
        if len(seen_maps)>int(BUDGETS.get('sitemap_files_per_domain_max',55)): break
    high=CFG.get("high_value_official_paths",[])
    def score(u: str) -> int:
        lu=u.lower()
        return sum(5 for x in high if x in lu)+sum(3 for x in ["spain","es-es","/es/","portugal","pt-pt","/pt/","iberia"] if x in lu)+sum(2 for x in ['customer','case','partner','award','press','news','success','story','blog'] if x in lu)
    result=sorted(list(dict.fromkeys(urls)),key=lambda u:(-score(u),u))[:max_urls]
    SITEMAP_CACHE[cache_key]=result
    return result


def fetch_page_metadata(url: str) -> dict | None:
    if url in PAGE_CACHE: return PAGE_CACHE[url]
    if should_stop(90): return None
    started=time.monotonic()
    try:
        r=SESSION.get(url,timeout=bounded_timeout(),allow_redirects=True)
        if r.status_code>=400 or "text/html" not in r.headers.get("content-type","text/html"):
            record_source_health(url, False, time.monotonic()-started, error=f'HTTP {r.status_code}')
            PAGE_CACHE[url]=None; return None
        text=r.text[:650000]
        mt=re.search(r"<title[^>]*>(.*?)</title>",text,re.I|re.S)
        md=re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\'](.*?)["\']',text,re.I|re.S)
        if not md: md=re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',text,re.I|re.S)
        canonical=re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']',text,re.I|re.S)
        if not canonical: canonical=re.search(r'<link[^>]+href=["\'](.*?)["\'][^>]+rel=["\']canonical["\']',text,re.I|re.S)
        published=''
        for pat in [r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|datePublished|date|publishdate)["\'][^>]+content=["\'](.*?)["\']',r'"datePublished"\s*:\s*"([^"]+)"',r'"dateModified"\s*:\s*"([^"]+)"']:
            m=re.search(pat,text,re.I|re.S)
            if m: published=clean(m.group(1)); break
        body=clean(text)
        desc=clean(md.group(1) if md else '')
        snippet=desc or body[:1000]
        row={"title":clean(mt.group(1) if mt else url.rsplit("/",1)[-1]),"snippet":snippet[:1600],"text":body[:18000],"url":clean(canonical.group(1) if canonical else r.url),"published":published,"engine":"official-sitemap"}
        record_source_health(url, True, time.monotonic()-started, int(bool(snippet)))
        PAGE_CACHE[url]=row; return row
    except Exception as exc:
        record_source_health(url, False, time.monotonic()-started, error=str(exc))
        PAGE_CACHE[url]=None; return None



COMMONCRAWL_INDEX_CACHE: str | None = None


def latest_commoncrawl_index() -> str | None:
    global COMMONCRAWL_INDEX_CACHE
    if COMMONCRAWL_INDEX_CACHE is not None: return COMMONCRAWL_INDEX_CACHE or None
    try:
        r=SESSION.get('https://index.commoncrawl.org/collinfo.json',timeout=min(TIMEOUT,20)); r.raise_for_status(); data=r.json()
        COMMONCRAWL_INDEX_CACHE=(data[0].get('cdx-api') or '').strip() if data else ''
    except Exception:
        COMMONCRAWL_INDEX_CACHE=''
    return COMMONCRAWL_INDEX_CACHE or None


def commoncrawl_domain_urls(domain: str, max_urls: int = 30) -> list[str]:
    """Use Common Crawl only as URL discovery. Any live page is re-fetched and rescored normally."""
    endpoint=latest_commoncrawl_index()
    if not endpoint or max_urls<=0: return []
    params={'url':f'{domain}/*','output':'json','filter':['status:200','mime:text/html'],'collapse':'urlkey'}
    high=[x.lower() for x in CFG.get('high_value_official_paths',[])]+['partner','customer','case','success','award','distributor','channel','reference','press','news','story']
    found=[]
    try:
        with SESSION.get(endpoint,params=params,timeout=max(TIMEOUT,35),stream=True) as r:
            r.raise_for_status()
            scanned=0
            for line in r.iter_lines(decode_unicode=True):
                if not line: continue
                scanned+=1
                if scanned>4000: break
                try: obj=json.loads(line)
                except Exception: continue
                u=clean(obj.get('url'))
                if not u or host(u)!=domain and not host(u).endswith('.'+domain): continue
                lu=u.lower()
                if any(k in lu for k in high): found.append(u)
                if len(found)>=max_urls*3: break
    except Exception:
        return []
    def score(u):
        lu=u.lower(); return sum(4 for k in high if k in lu)+sum(3 for k in ['spain','portugal','iberia','/es/','/pt/'] if k in lu)
    return sorted(dict.fromkeys(found),key=lambda u:(-score(u),u))[:max_urls]


def commoncrawl_official_evidence(vendors: list[str], budget: int) -> list[dict]:
    if budget<=0: return []
    domains=CFG.get('vendor_domains',{}); cov=previous_gap_priority()
    ranked=sorted([v for v in vendors if domains.get(v)],key=lambda v:(cov.get(v,0),v))
    vendor_limit=max(1,min(len(ranked),int(BUDGETS.get('commoncrawl_vendor_limit',12))))
    ranked=ranked[:vendor_limit]; per=max(5,min(30,budget//max(1,len(ranked))))
    targets=[]
    with ThreadPoolExecutor(max_workers=min(6,WORKERS)) as ex:
        futs={ex.submit(commoncrawl_domain_urls,domains[v],per):v for v in ranked}
        for fut in as_completed(futs):
            v=futs[fut]
            try: urls=fut.result()
            except Exception: urls=[]
            for u in urls: targets.append((v,u))
    targets=targets[:budget]; out=[]
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(fetch_page_metadata,u):(v,u) for v,u in targets}
        for fut in as_completed(futs):
            v,u=futs[fut]
            try: row=fut.result()
            except Exception: row=None
            if not row: continue
            row.update({'vendor':v,'country':infer_country_from_url(row.get('url','')) or 'ALL','kind':'official-commoncrawl-discovery','engine':'commoncrawl-url-discovery'})
            out.append(row)
    return out


def official_portal_seed_evidence() -> list[dict]:
    """Fetch high-value official partner pages before broad discovery.

    The page body is correlated with the known Iberia ecosystem. This is much
    higher-yield than waiting for a sitemap/search engine to surface the page,
    while remaining conservative: only explicit partner/channel context is
    accepted and every resulting candidate keeps the exact official URL.
    """
    seeds=V36_PORTALS.get('seeds',[]) or []
    if not seeds: return []
    context_terms=[norm(x) for x in (V36_PORTALS.get('partner_context_terms',[]) or [])]
    known_integrators=list(dict.fromkeys(CFG.get('known_integrators',[])+discovered_integrators(400)))
    known_distributors=list(dict.fromkeys(CFG.get('known_distributors',[])))
    targets=seeds[:int(BUDGETS.get('portal_seed_pages_max',max(20,len(seeds))))]
    pages=[]
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(fetch_page_metadata,x.get('url')):x for x in targets if x.get('url')}
        for fut in as_completed(futs):
            seed=futs[fut]
            try: page=fut.result()
            except Exception: page=None
            if page: pages.append((seed,page))
    out=[]
    for seed,page in pages:
        body=norm(f"{page.get('title','')} {page.get('snippet','')} {page.get('text','')}")
        if context_terms and not any(t and t in body for t in context_terms):
            continue
        vendor=seed.get('vendor'); country=seed.get('country') or 'ALL'
        # Exact entity-name matching is intentionally conservative. The expanded
        # source universe ensures smaller Iberia partners can still be found.
        matches=[]
        for entity in known_integrators:
            ne=norm(entity)
            if len(ne)>=3 and ne in body: matches.append(('integrator',entity))
        for entity in known_distributors:
            ne=norm(entity)
            if len(ne)>=3 and ne in body: matches.append(('distributor',entity))
        seen=set()
        for entity_kind,entity in matches:
            key=(entity_kind,norm(entity))
            if key in seen: continue
            seen.add(key)
            raw=page.get('text','') or page.get('snippet','') or ''
            nr=norm(raw); ne=norm(entity); pos=nr.find(ne)
            # Keep a compact context around the matched company when possible.
            snippet=page.get('snippet','')
            if pos>=0:
                start=max(0,pos-220); end=min(len(raw),pos+len(str(entity))+420)
                snippet=clean(raw[start:end])
            row=dict(page)
            row.update({'vendor':vendor,'country':country,'kind':'official-partner-portal-seed','engine':'official-partner-portal-seed','winner':entity if entity_kind=='integrator' else None,'distributor':entity if entity_kind=='distributor' else None,'snippet':snippet,'portalKind':seed.get('kind'),'sourceEntity':entity})
            out.append(row)
    return out


def official_sitemap_evidence(vendors: list[str]) -> list[dict]:
    domains = CFG.get("vendor_domains", {})
    budget = int(BUDGETS.get("sitemap_pages_max", 1400))
    per_vendor = max(12, min(55, budget // max(1, len(vendors))))
    targets = []
    domain_limit=int(BUDGETS.get('vendor_domains_per_run',len(vendors)))
    selected=adaptive_source_selection([v for v in vendors if domains.get(v)],domain_limit,'vendor-domains',lambda v:domains[v])
    with ThreadPoolExecutor(max_workers=min(WORKERS, 10)) as ex:
        futs={ex.submit(discover_sitemap_urls,domains[v],per_vendor):v for v in selected}
        for fut in as_completed(futs):
            vendor=futs[fut]
            try: urls=fut.result()
            except Exception: urls=[]
            for u in urls:
                if any(x in u.lower() for x in CFG.get("high_value_official_paths", [])):
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
    learned=load_json_state(LEARNING_OUT,{}).get('sources',{})
    ranked_entities=sorted(entity_domains.items(),key=lambda x:-(float(learned.get(x[1],{}).get('primaryHits',0))+1)/(float(learned.get(x[1],{}).get('seen',0))+2))
    limit=int(BUDGETS.get(f'{entity_kind}_domains_per_run',BUDGETS.get('ecosystem_domains_per_run',len(ranked_entities))))
    selected=adaptive_source_selection(ranked_entities,limit,f'{entity_kind}-domains',lambda x:x[1])
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(discover_sitemap_urls,domain,per_entity):entity for entity,domain in selected}
        for fut in as_completed(futs):
            entity=futs[fut]
            try: urls=fut.result()
            except Exception: urls=[]
            for u in urls:
                if any(x in u.lower() for x in CFG.get('high_value_official_paths',[])):
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
            text=norm(f"{row.get('title','')} {row.get('snippet','')} {row.get('text','')} {row.get('url','')}")
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
    learned=load_json_state(LEARNING_OUT,{}).get('sources',{})
    ranked_domains=sorted(domains.items(),key=lambda x:-(float(learned.get(x[1],{}).get('primaryHits',0))+1)/(float(learned.get(x[1],{}).get('seen',0))+2))
    selected=adaptive_source_selection(ranked_domains,int(BUDGETS.get('analyst_domains_per_run',len(ranked_domains))),'analyst-domains',lambda x:x[1])
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(discover_sitemap_urls,domain,per):analyst for analyst,domain in selected}
        for fut in as_completed(futs):
            analyst=futs[fut]
            try: urls=fut.result()
            except Exception: urls=[]
            for u in urls:
                if any(k.replace(' ','-') in u.lower() or k in u.lower() for k in keywords): targets.append((analyst,u))
    targets=targets[:budget]
    with ThreadPoolExecutor(max_workers=min(WORKERS,10)) as ex:
        futs={ex.submit(fetch_page_metadata,u):(a,u) for a,u in targets}
        for fut in as_completed(futs):
            analyst,u=futs[fut]
            try: row=fut.result()
            except Exception: row=None
            if not row: continue
            text=norm(f"{row.get('title','')} {row.get('snippet','')} {row.get('text','')} {row.get('url','')}")
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


def procurement_change_events(prev: dict, current: list[dict]) -> list[dict]:
    """Detect material changes in public-procurement demand without claiming market share."""
    old={(x.get('country'),x.get('technologyId')):x for x in prev.get('procurementMarket',[]) if x.get('country') and x.get('technologyId')}
    cur={(x.get('country'),x.get('technologyId')):x for x in current if x.get('country') and x.get('technologyId')}
    out=[]
    delta_min=int(DEEP.get('change_detection',{}).get('material_procurement_demand_delta',15))
    for key,row in cur.items():
        before=old.get(key)
        if not before: continue
        a=int(before.get('demandIndex',0)); b=int(row.get('demandIndex',0))
        if abs(b-a)>=delta_min:
            out.append({'type':'public-procurement-demand','country':row.get('country'),'technology':row.get('technology'),'technologyId':row.get('technologyId'),'title':'Cambio material en señal de demanda pública','from':a,'to':b,'knownValueEUR':row.get('knownValueEUR',0),'detectedAt':NOW.isoformat()})
        old_buy={norm(x.get('name')) for x in before.get('topBuyers',[])[:8] if x.get('name')}
        for x in row.get('topBuyers',[])[:5]:
            if x.get('name') and norm(x['name']) not in old_buy:
                out.append({'type':'public-procurement-buyer','country':row.get('country'),'technology':row.get('technology'),'technologyId':row.get('technologyId'),'title':'Nuevo comprador público relevante detectado','entity':x.get('name'),'signals':x.get('signals'),'detectedAt':NOW.isoformat()})
        old_win={norm(x.get('name')) for x in before.get('topWinners',[])[:8] if x.get('name')}
        for x in row.get('topWinners',[])[:5]:
            if x.get('name') and norm(x['name']) not in old_win:
                out.append({'type':'public-procurement-winner','country':row.get('country'),'technology':row.get('technology'),'technologyId':row.get('technologyId'),'title':'Nuevo adjudicatario / integrador relevante detectado','entity':x.get('name'),'signals':x.get('signals'),'detectedAt':NOW.isoformat()})
    return out[:100]


def compute_changes(prev: dict, channels, integrators, customers, coverage, procurement_market=None, ended_channels=None) -> list[dict]:
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
        # Detect relationships that disappeared from the active graph. This is a signal, not proof of termination.
        if kind=='channel':
            for key in sorted(old-new)[:80]:
                vendor,country,name=key
                changes.append({'type':'channel-missing','vendor':vendor,'country':country,'title':'Relación de canal ya no confirmada en el dataset activo','entity':name,'status':'needs-validation','detectedAt':NOW.isoformat()})
    for row in ended_channels or []:
        changes.append({'type':'channel-ended','vendor':row.get('vendor'),'country':row.get('country'),'title':'Señal pública de fin de distribución','entity':row.get('distributor'),'confidence':row.get('confidence'),'url':row.get('url'),'evidenceId':row.get('evidenceId'),'detectedAt':NOW.isoformat()})
    prev_cov={r.get('vendor'):int(r.get('coverage',0)) for r in prev.get('coverage',[]) if r.get('vendor')}
    delta_min=int(DEEP.get('change_detection',{}).get('material_coverage_delta',8))
    for r in coverage:
        if r['vendor'] in prev_cov and abs(r['coverage']-prev_cov[r['vendor']])>=delta_min:
            changes.append({'type':'coverage','vendor':r['vendor'],'title':'Cambio material de cobertura de inteligencia','from':prev_cov[r['vendor']],'to':r['coverage'],'detectedAt':NOW.isoformat()})
    if procurement_market is not None:
        changes.extend(procurement_change_events(prev,procurement_market))
    return changes[:350]


def detect_conflicts(evidence: list[dict], channels: list[dict]) -> list[dict]:
    terms=[norm(x) for x in DEEP.get('change_detection',{}).get('conflict_terms',[])]
    channel_words=[norm(x) for x in ['distribution','distributor','channel','mayorista','distribuidor','distribución','distribuicao','distribuição']]
    out=[]
    for e in evidence:
        text=norm(f"{e.get('title','')} {e.get('snippet','')} {e.get('text','')}")
        if not any(t and t in text for t in terms): continue
        if not any(w in text for w in channel_words): continue
        vendor=e.get('vendor')
        if not vendor: continue
        impacted=[c for c in channels if c.get('vendor')==vendor and (not e.get('country') or c.get('country')==e.get('country'))]
        mentioned=[x for x in impacted if norm(x.get('distributor')) and norm(x.get('distributor')) in text]
        out.append({'vendor':vendor,'country':e.get('country'),'title':e.get('title'),'url':e.get('url'),'evidenceId':e.get('id'),'confidence':e.get('confidence'),'sourceTier':e.get('sourceTier'),'possibleConflictWith':[f"{x.get('country')}:{x.get('distributor')}" for x in impacted[:8]],'explicitDistributorMatches':[f"{x.get('country')}:{x.get('distributor')}" for x in mentioned[:8]],'status':'candidate-channel-termination' if mentioned else 'needs-validation'})
    return out[:160]


def resolve_channel_lifecycle(channels: list[dict], conflicts: list[dict]) -> tuple[list[dict],list[dict]]:
    """Remove only strongly evidenced, explicitly named ended relations from the ACTIVE graph; keep them in history."""
    ended=[]; ended_keys=set()
    for c in conflicts:
        if c.get('status')!='candidate-channel-termination': continue
        conf=int(c.get('confidence') or 0); tier=c.get('sourceTier')
        strong=(tier in {'official-company','regulator','public-open-data'} and conf>=72) or conf>=86
        if not strong: continue
        for token in c.get('explicitDistributorMatches',[]):
            try: country,dist=token.split(':',1)
            except ValueError: continue
            key=(c.get('vendor'),country,norm(dist)); ended_keys.add(key)
            row=next((x for x in channels if (x.get('vendor'),x.get('country'),norm(x.get('distributor')))==key),None)
            if row:
                h=dict(row); h.update({'status':'ended-public-signal','active':False,'endedDetectedAt':NOW.isoformat(),'evidenceId':c.get('evidenceId'),'url':c.get('url'),'confidence':max(int(row.get('confidence',0)),conf)})
                ended.append(h)
    active=[]
    for row in channels:
        key=(row.get('vendor'),row.get('country'),norm(row.get('distributor')))
        if key in ended_keys: continue
        x=dict(row); x['active']=True; x.setdefault('status','public-signal'); active.append(x)
    return active,ended


def write_light_history(payload: dict, changes: list[dict]) -> None:
    snap={'generatedAt':payload.get('generatedAt'),'profile':PROFILE,'derived':payload.get('derived'),'coverage':payload.get('coverage'),'gaps':payload.get('gaps'),'changes':changes,'conflicts':payload.get('conflicts',[])}
    path=HISTORY/f"snapshot-{TODAY}-{PROFILE}.json"; path.write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8')
    # Keep repository history bounded.
    files=sorted(HISTORY.glob(f"snapshot-*-{PROFILE}.json"), key=lambda x:x.name, reverse=True)
    keep=int(DEEP.get('history',{}).get('light_snapshots_daily' if PROFILE=='daily' else 'light_snapshots_deep',30))
    for old in files[keep:]:
        try: old.unlink()
        except Exception: pass

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


def lname(tag: str) -> str:
    return str(tag or '').split('}', 1)[-1]


def texts_at(node: ET.Element, path: str) -> list[str]:
    vals=[]
    try:
        for x in node.findall(path):
            t=clean(x.text)
            if t: vals.append(t)
    except Exception:
        pass
    return vals


def first_at(node: ET.Element, paths: list[str], default: str = '') -> str:
    for path in paths:
        vals=texts_at(node,path)
        if vals: return vals[0]
    return default


def parse_number(value) -> float | None:
    if value is None: return None
    s=clean(value).replace('\xa0',' ').replace('€','').replace('$','').strip()
    if not s: return None
    # Handle common Iberian thousands/decimal conventions conservatively.
    s=re.sub(r'[^0-9,.-]','',s)
    if not s: return None
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s=s.replace('.','').replace(',','.')
        else:
            s=s.replace(',','')
    elif ',' in s:
        parts=s.split(',')
        s=''.join(parts[:-1])+'.'+parts[-1] if len(parts[-1]) in {1,2} else ''.join(parts)
    try: return float(s)
    except Exception: return None


def clean_entity_name(value: str) -> str:
    s=clean(value)
    # Portal BASE often prefixes Portuguese NIF: "123456789 - Empresa".
    s=re.sub(r'^\s*\d{8,10}\s*[-–:]\s*','',s)
    return s[:240]


def classify_procurement(cpv_values: list[str], text: str) -> list[dict]:
    cpvs=[re.sub(r'\D','',str(x or '')) for x in cpv_values if x]
    nt=norm(text)
    matches=[]
    for bucket in PROC_TAX.get('technologyBuckets',[]):
        cpv_hit=any(any(c.startswith(str(prefix)) for prefix in bucket.get('cpvPrefixes',[])) for c in cpvs)
        cpv_only_hit=any(any(c.startswith(str(prefix)) for prefix in bucket.get('cpvOnlyPrefixes',[])) for c in cpvs)
        kw_hits=[k for k in bucket.get('keywords',[]) if norm(k) and norm(k) in nt]
        if kw_hits or cpv_only_hit:
            confidence=94 if cpv_hit and kw_hits else 82 if cpv_only_hit else min(78,55+len(kw_hits)*7)
            matches.append({'id':bucket['id'],'name':bucket['name'],'themeIds':bucket.get('themeIds',[]),'confidence':confidence,'cpvHit':cpv_hit,'keywordHits':kw_hits[:6]})
    return sorted(matches,key=lambda x:(-x['confidence'],x['name']))[:5]


def infer_procurement_sector(buyer: str, text: str) -> str:
    nt=norm(f'{buyer} {text}')
    for rule in PROC_TAX.get('sectorRules',[]):
        if any(norm(k) in nt for k in rule.get('keywords',[])):
            return rule['sector']
    return 'Sector público'


def parse_atom_entries(xml_bytes: bytes) -> list[ET.Element]:
    try: root=ET.fromstring(xml_bytes)
    except Exception: return []
    return list(root.findall('.//{*}entry'))


def parse_placsp_entry(entry: ET.Element, source_url: str, country: str='ES') -> dict:
    title=first_at(entry,['./{*}title','.//{*}ProcurementProject/{*}Name','.//{*}ProcurementProject/{*}Description'],'PLACSP procurement signal')
    entry_id=first_at(entry,['./{*}id'])
    link=''
    for x in entry.findall('./{*}link'):
        href=x.attrib.get('href') or x.attrib.get('ref')
        if href and ('licit' in href.lower() or not link): link=href
    url=link or entry_id or source_url
    published=first_at(entry,['./{*}updated','./{*}published','.//{*}IssueDate','.//{*}AwardDate'])
    expediente=first_at(entry,['.//{*}ContractFolderID','.//{*}ID'])
    status=first_at(entry,['.//{*}ContractFolderStatusCode','.//{*}ResultCode'])
    buyer=first_at(entry,[
        './/{*}ContractingParty/{*}Party/{*}PartyName/{*}Name',
        './/{*}ContractingParty/{*}PartyName/{*}Name',
        './/{*}ContractingParty//{*}PartyName/{*}Name'
    ])
    obj=first_at(entry,['.//{*}ProcurementProject/{*}Name','.//{*}ProcurementProject/{*}Description'],title)
    desc=' '.join(texts_at(entry,'.//{*}ProcurementProject/{*}Description')[:3])
    cpvs=texts_at(entry,'.//{*}RequiredCommodityClassification/{*}ItemClassificationCode')
    if not cpvs: cpvs=texts_at(entry,'.//{*}ItemClassificationCode')
    estimated=None; currency='EUR'
    for path in ['.//{*}EstimatedOverallContractAmount','.//{*}BudgetAmount/{*}TaxExclusiveAmount','.//{*}BudgetAmount/{*}TotalAmount']:
        nodes=entry.findall(path)
        if nodes:
            estimated=parse_number(nodes[0].text); currency=nodes[0].attrib.get('currencyID','EUR'); break
    winners=[]; awarded=[]; award_dates=[]
    for tr in entry.findall('.//{*}TenderResult'):
        names=texts_at(tr,'.//{*}WinningParty/{*}PartyName/{*}Name')
        if not names: names=texts_at(tr,'.//{*}WinningParty//{*}Name')
        for n in names:
            cn=clean_entity_name(n)
            if cn and cn not in winners: winners.append(cn)
        award_dates.extend(texts_at(tr,'.//{*}AwardDate'))
        for path in ['.//{*}AwardedTenderedProject/{*}LegalMonetaryTotal/{*}TaxExclusiveAmount','.//{*}AwardedTenderedProject/{*}LegalMonetaryTotal/{*}PayableAmount']:
            for an in tr.findall(path):
                val=parse_number(an.text)
                if val is not None: awarded.append((val,an.attrib.get('currencyID','EUR')))
    awarded_value=max((x[0] for x in awarded),default=None)
    if awarded: currency=awarded[0][1] or currency
    all_text=clean(' '.join(entry.itertext()))
    tech=classify_procurement(cpvs,f'{title} {obj} {desc} {all_text[:8000]}')
    sector=infer_procurement_sector(buyer,f'{title} {obj} {desc}')
    return {'title':title,'url':url,'snippet':clean(f'{obj}. {desc}')[:2200],'published':published,'engine':'placsp-open-data','country':country,'buyer':clean_entity_name(buyer),'winners':winners,'winner':winners[0] if winners else '', 'procurement':True,'contractId':expediente,'status':status,'cpv':cpvs[:12],'estimatedValue':estimated,'awardedValue':awarded_value,'currency':currency,'awardDate':award_dates[0] if award_dates else '', 'technologyMatches':tech,'sector':sector,'object':obj}


def month_sequence(months_back: int) -> list[tuple[int,int]]:
    y,m=NOW.year,NOW.month; out=[]
    for _ in range(max(1,months_back)):
        out.append((y,m)); m-=1
        if m==0: m=12; y-=1
    return out


def spanish_procurement_urls() -> list[tuple[str,str]]:
    cfg=DEEP.get('public_procurement',{}).get('spain',{})
    months=int(BUDGETS.get('spain_procurement_months',1 if PROFILE=='daily' else 6))
    rows=[]
    for y,m in month_sequence(months):
        ym=f'{y}{m:02d}'
        rows.append(('sector-publico',cfg.get('monthly_pattern','https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_{yyyymm}.zip').format(yyyymm=ym)))
        rows.append(('agregadas',cfg.get('aggregation_monthly_pattern','https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1044/PlataformasAgregadasSinMenores_{yyyymm}.zip').format(yyyymm=ym)))
    return rows


def official_spain_procurement_rows(vendors: list[str]) -> list[dict]:
    """Parse recent official PLACSP and aggregated-platform Atom packages structurally.

    We retain both vendor-specific evidence and technology-market demand signals. A
    technology match without a vendor mention is not attributed to any vendor.
    """
    vendor_terms={v:[norm(a) for a in aliases_for(v) if len(norm(a))>=3] for v in vendors}
    out=[]; max_rows=int(BUDGETS.get('spain_procurement_rows_max',5000))
    for source_kind,url in spanish_procurement_urls():
        try:
            r=SESSION.get(url,timeout=max(45,TIMEOUT),stream=True); r.raise_for_status(); content=r.content
            if len(content)>int(BUDGETS.get('procurement_download_max_bytes',160_000_000)): continue
            z=zipfile.ZipFile(io.BytesIO(content))
        except Exception as exc:
            print('PLACSP download error',url,exc); continue
        names=[n for n in z.namelist() if n.lower().endswith(('.atom','.xml'))]
        for name in names[:int(BUDGETS.get('spain_atom_files_max',160))]:
            try: entries=parse_atom_entries(z.read(name))
            except Exception: continue
            for entry in entries:
                rec=parse_placsp_entry(entry,url,'ES'); full=norm(' '.join(entry.itertext()))
                matched=[v for v,terms in vendor_terms.items() if any(t and t in full for t in terms)]
                if not matched and not rec.get('technologyMatches'): continue
                if matched:
                    for vendor in matched[:5]:
                        x=dict(rec); x['vendor']=vendor; x['procurementAttribution']='vendor-explicit-public-record'; x['sourceKind']=source_kind; out.append(x)
                else:
                    rec['vendor']=None; rec['procurementAttribution']='technology-market-signal-only'; rec['sourceKind']=source_kind; out.append(rec)
                if len(out)>=max_rows: return out
    return out


def _pick_field(row: dict, patterns: list[str]) -> str:
    nr={norm(k):v for k,v in row.items()}
    for pattern in patterns:
        np=norm(pattern)
        for k,v in nr.items():
            if np==k or np in k:
                if clean(v): return clean(v)
    return ''


def parse_csv_blob(blob: bytes) -> list[dict]:
    text=''
    for enc in ('utf-8-sig','utf-8','cp1252','latin-1'):
        try:
            text=blob.decode(enc); break
        except Exception: continue
    if not text: return []
    sample=text[:12000]
    try: dialect=csv.Sniffer().sniff(sample,delimiters=';,\t|')
    except Exception:
        dialect=csv.excel; dialect.delimiter=';'
    try: return list(csv.DictReader(io.StringIO(text),dialect=dialect))
    except Exception: return []


def _resource_payloads(content: bytes, url: str) -> list[bytes]:
    if url.lower().endswith('.zip') or content[:2]==b'PK':
        try:
            z=zipfile.ZipFile(io.BytesIO(content)); return [z.read(n) for n in z.namelist() if n.lower().endswith(('.csv','.txt'))][:40]
        except Exception: return []
    return [content]


def dados_gov_pt_contract_rows(vendors: list[str]) -> list[dict]:
    endpoint=DEEP.get('engines',{}).get('dados_gov_pt',{}).get('endpoint')
    q=DEEP.get('public_procurement',{}).get('portugal',{}).get('dataset_query','Contratos Públicos Portal Base IMPIC contratos')
    try: data=get_json(endpoint,params={'q':q,'page_size':20})
    except Exception: return []
    datasets=data.get('data',[]) or data.get('results',[]) or []
    resources=[]
    for ds in datasets[:8]: resources.extend(ds.get('resources') or [])
    def rscore(r):
        s=norm(f"{r.get('title','')} {r.get('url','')} {r.get('format','')}")
        return (30 if str(NOW.year) in s else 0)+(14 if 'csv' in s else 0)+(10 if 'zip' in s else 0)+int(bool(r.get('latest')))*4
    resources=sorted(resources,key=rscore,reverse=True)[:int(BUDGETS.get('portugal_resources_max',10))]
    terms={v:[norm(a) for a in aliases_for(v) if len(norm(a))>=3] for v in vendors}; out=[]; max_rows=int(BUDGETS.get('portugal_procurement_rows_max',5000))
    for res in resources:
        url=res.get('url') or res.get('latest')
        if not url: continue
        try:
            r=SESSION.get(url,timeout=max(50,TIMEOUT)); r.raise_for_status(); content=r.content
            if len(content)>int(BUDGETS.get('procurement_download_max_bytes',160_000_000)): continue
        except Exception as exc:
            print('dados.gov.pt resource error',url,exc); continue
        for blob in _resource_payloads(content,url):
            for row in parse_csv_blob(blob):
                buyer=clean_entity_name(_pick_field(row,['adjudicante','entidade adjudicante','contracting authority','buyer']))
                winner=clean_entity_name(_pick_field(row,['adjudicatarios','adjudicatário','adjudicatario','winner','fornecedor']))
                obj=_pick_field(row,['objecto contrato','objeto contrato','descricao contrato','descrição contrato','designacao contrato','designação contrato','object'])
                cpv_raw=_pick_field(row,['cpv','codigo cpv','código cpv']); cpvs=re.findall(r'\d{8}',cpv_raw)
                published=_pick_field(row,['data publicacao','data publicação','data celebracao','data celebração','date'])
                amount=parse_number(_pick_field(row,['preco contratual','preço contratual','valor contrato','valor contratual','amount']))
                cid=_pick_field(row,['idcontrato','id contrato','numero contrato','número contrato'])
                url_row=_pick_field(row,['url','link']) or url
                line=' '.join(str(v or '') for v in row.values())
                nl=norm(line); matched=[v for v,ats in terms.items() if any(a and a in nl for a in ats)]
                tech=classify_procurement(cpvs,f'{obj} {line[:8000]}')
                if not matched and not tech: continue
                rec={'title':obj or 'Portal BASE / IMPIC public contract signal','url':url_row,'snippet':clean(f'{obj}. Adjudicante: {buyer}. Adjudicatário: {winner}.')[:2200],'published':published,'engine':'dados-gov-pt','country':'PT','buyer':buyer,'winner':winner,'winners':[winner] if winner else [],'procurement':True,'contractId':cid,'cpv':cpvs[:12],'awardedValue':amount,'estimatedValue':None,'currency':'EUR','technologyMatches':tech,'sector':infer_procurement_sector(buyer,obj),'object':obj}
                if matched:
                    for vendor in matched[:5]:
                        x=dict(rec); x['vendor']=vendor; x['procurementAttribution']='vendor-explicit-public-record'; out.append(x)
                else:
                    rec['vendor']=None; rec['procurementAttribution']='technology-market-signal-only'; out.append(rec)
                if len(out)>=max_rows: return out
    return out


def ted_search(vendor: str, country: str) -> list[dict]:
    code=DEEP.get('public_procurement',{}).get('ted',{}).get('countries',{}).get(country)
    if not code: return []
    alias=aliases_for(vendor)[0]; query=f'FT~"{alias}" AND CY={code}'
    fields=DEEP['public_procurement']['ted']['fields']
    body={'query':query,'fields':fields,'page':1,'limit':min(250,int(BUDGETS.get('ted_results_per_query',180))),'scope':'ALL','checkQuerySyntax':False,'paginationMode':'PAGE_NUMBER'}
    try:
        r=SESSION.post(DEEP['engines']['ted']['endpoint'],json=body,timeout=TIMEOUT); r.raise_for_status(); data=r.json()
    except Exception: return []
    records=data.get('notices') or data.get('results') or data.get('items') or []
    out=[]
    for rec in records:
        flat=flatten_json(rec)
        def pick(parts):
            return next((v for k,v in flat.items() if any(p in k.lower() for p in parts) and clean(v)), '')
        title=pick(['notice-title','contract-title']) or 'TED procurement notice'; buyer=clean_entity_name(pick(['buyer-name'])); winner=clean_entity_name(pick(['winner-name']))
        pubno=pick(['publication-number']); published=pick(['publication-date']); cpv_text=' '.join(v for k,v in flat.items() if 'classification-cpv' in k.lower() or 'main-classification' in k.lower()); cpvs=re.findall(r'\d{8}',cpv_text)
        value=parse_number(pick(['contract-value','tender-value','framework-value','estimated-value']))
        url=f'https://ted.europa.eu/en/notice/{pubno}/html' if pubno else 'https://ted.europa.eu/'
        tech=classify_procurement(cpvs,title)
        out.append({'title':title,'url':url,'snippet':clean(f'Buyer: {buyer}. Winner: {winner}. Vendor search: {vendor}.'),'published':published,'engine':'ted','vendor':vendor,'country':country,'buyer':buyer,'winner':winner,'winners':[winner] if winner else [],'procurement':True,'contractId':pubno,'cpv':cpvs[:12],'awardedValue':value,'currency':'EUR','technologyMatches':tech,'sector':infer_procurement_sector(buyer,title),'object':title,'procurementAttribution':'vendor-explicit-search-result'})
    return out


def procurement_market_aggregate(evidence: list[dict]) -> list[dict]:
    rows=defaultdict(lambda:{'count':0,'values':[],'buyers':Counter(),'winners':Counter(),'vendors':Counter(),'sectors':Counter(),'dates':[],'themeIds':set(),'ids':set()})
    for e in evidence:
        if e.get('evidenceType')!='procurement': continue
        cc=e.get('country') or ('ES' if 'Spain' in str(e.get('scope')) else 'PT' if 'Portugal' in str(e.get('scope')) else '')
        if cc not in {'ES','PT'}: continue
        techs=e.get('technologyMatches') or []
        for t in techs:
            tid=t.get('id') if isinstance(t,dict) else str(t)
            if not tid: continue
            k=(cc,tid); r=rows[k]; r['count']+=1; r['ids'].add(e.get('id'))
            val=e.get('awardedValue') or e.get('estimatedValue')
            if isinstance(val,(int,float)) and 0<val<10_000_000_000: r['values'].append(float(val))
            if e.get('buyer'): r['buyers'][clean_entity_name(e['buyer'])]+=1
            for w in (e.get('winners') or ([e.get('winner')] if e.get('winner') else [])):
                if w: r['winners'][clean_entity_name(w)]+=1
            if e.get('vendor'): r['vendors'][e['vendor']]+=1
            if e.get('sector'): r['sectors'][e['sector']]+=1
            if e.get('published'): r['dates'].append(str(e['published']))
            if isinstance(t,dict): r['themeIds'].update(t.get('themeIds') or [])
    max_count=max((r['count'] for r in rows.values()),default=1); out=[]
    names={x['id']:x['name'] for x in PROC_TAX.get('technologyBuckets',[])}
    for (cc,tid),r in rows.items():
        count_score=min(100,round((r['count']/max_count)**0.5*100)); value_total=sum(r['values']); value_score=min(100,round((value_total/50_000_000)**0.35*100)) if value_total else 0
        diversity=min(100,30+len(r['buyers'])*4+len(r['winners'])*3+len(r['sectors'])*5)
        demand=clamp(count_score*.55+value_score*.20+diversity*.25)
        out.append({'country':cc,'technologyId':tid,'technology':names.get(tid,tid),'themeIds':sorted(r['themeIds']),'signalCount':r['count'],'knownValueEUR':round(value_total,2),'demandIndex':demand,'topBuyers':[{'name':n,'signals':c} for n,c in r['buyers'].most_common(12)],'topWinners':[{'name':n,'signals':c} for n,c in r['winners'].most_common(12)],'vendorMentions':[{'name':n,'signals':c} for n,c in r['vendors'].most_common(10)],'sectors':[{'name':n,'signals':c} for n,c in r['sectors'].most_common(8)],'latestDate':max(r['dates']) if r['dates'] else ''})
    return sorted(out,key=lambda x:(-x['demandIndex'],x['country'],x['technology']))


# ----------------------------- Query planning -----------------------------

def previous_gap_priority() -> dict[str, int]:
    try:
        prev=json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return {x.get('vendor'): int(x.get('coverage',0)) for x in prev.get('coverage',[]) if x.get('vendor')}


def previous_gap_dimensions() -> dict[str, dict]:
    try: prev=json.loads(OUT.read_text(encoding='utf-8'))
    except Exception: return {}
    return {x.get('vendor'):x.get('dimensions',{}) for x in prev.get('coverage',[]) if x.get('vendor')}


def discovered_integrators(limit: int = 160) -> list[str]:
    """Grow the integrator universe from both explicit vendor relations and public-procurement winners."""
    try: prev=json.loads(OUT.read_text(encoding='utf-8'))
    except Exception: return []
    scored=[]
    for x in prev.get('integratorSignals',[]):
        n=clean(x.get('name'))
        if int(x.get('confidence',0))>=68 and n: scored.append((100+int(x.get('confidence',0)),n))
    for bucket in prev.get('procurementMarket',[]):
        for pos,x in enumerate(bucket.get('topWinners',[])[:12]):
            n=clean(x.get('name'))
            if n: scored.append((90-pos*3+min(20,int(x.get('signals',0))*2),n))
    names=[]
    for _,n in sorted(scored,key=lambda z:(-z[0],norm(z[1]))):
        if n and n not in names and len(n)>=3: names.append(n)
        if len(names)>=limit: break
    return names


def discovered_buyers(limit: int = 120) -> list[dict]:
    """Return public buyers discovered from procurement, retaining country/technology context for follow-up research."""
    try: prev=json.loads(OUT.read_text(encoding='utf-8'))
    except Exception: return []
    rows=[]; seen=set()
    for bucket in sorted(prev.get('procurementMarket',[]),key=lambda x:-int(x.get('demandIndex',0))):
        for pos,x in enumerate(bucket.get('topBuyers',[])[:10]):
            n=clean(x.get('name')); key=(norm(n),bucket.get('country'),bucket.get('technologyId'))
            if not n or key in seen: continue
            seen.add(key); rows.append({'name':n,'country':bucket.get('country'),'technologyId':bucket.get('technologyId'),'technology':bucket.get('technology'),'priority':int(bucket.get('demandIndex',0))+max(0,20-pos*2)+min(15,int(x.get('signals',0))*2)})
    rows.sort(key=lambda x:(-x['priority'],x['country'] or '',norm(x['name'])))
    return rows[:limit]


def dynamic_entity_catalog(channels: list[dict], integrators: list[dict], procurement_market: list[dict]) -> dict:
    """Promote repeatedly observed actors without silently declaring them verified."""
    def aggregate(rows, name_key, kind):
        buckets=defaultdict(list)
        for row in rows:
            name=clean_entity_name(row.get(name_key,''))
            if name: buckets[norm(name)].append((name,row))
        out=[]
        for values in buckets.values():
            name=Counter(x[0] for x in values).most_common(1)[0][0];signals=[x[1] for x in values]
            urls=list(dict.fromkeys(x.get('url') for x in signals if x.get('url')));domains=list(dict.fromkeys(host(x) for x in urls if host(x)))
            countries=sorted(set(x.get('country') for x in signals if x.get('country') in {'ES','PT','IBERIA'}));vendors=sorted(set(x.get('vendor') for x in signals if x.get('vendor')))
            independent=len(set(domains));confidence=max([int(x.get('confidence',0)) for x in signals] or [0]);promoted=independent>=2 and confidence>=70
            out.append({'name':name,'kind':kind,'countries':countries,'vendors':vendors,'signalCount':len(signals),'independentSources':independent,'confidence':confidence,'status':'promoted-public-candidate' if promoted else 'discovery-candidate','domain':domains[0] if len(domains)==1 else None,'sourceUrls':urls[:8],'lastSeenAt':NOW.isoformat()})
        return sorted(out,key=lambda x:(x['status']!='promoted-public-candidate',-x['independentSources'],-x['signalCount'],norm(x['name'])))
    winners=[]
    for bucket in procurement_market:
        for row in bucket.get('topWinners',[]): winners.append({'name':row.get('name'),'country':bucket.get('country'),'vendor':None,'confidence':78,'url':row.get('url')})
    return {'version':1,'generatedAt':NOW.isoformat(),'policy':'Discovery candidates are not executive evidence. Promotion needs at least two independent public domains and confidence >=70.','distributors':aggregate(channels,'distributor','distributor'),'integrators':aggregate([*integrators,*winners],'name','integrator')}


def query_gap_boost(vendor: str, country: str, intent: str, dims: dict[str,dict]) -> int:
    d=dims.get(vendor,{})
    boost=0
    if country=='ES':
        if intent in {'channel','channel_changes'} and d.get('channelES') is False: boost+=38
        if intent in {'ecosystem','partner_capability'} and d.get('integratorES') is False: boost+=38
        if intent in {'customers','customer_verticals'} and d.get('customerES') is False: boost+=38
    if country=='PT':
        if intent in {'channel','channel_changes'} and d.get('channelPT') is False: boost+=42
        if intent in {'ecosystem','partner_capability'} and d.get('integratorPT') is False: boost+=42
        if intent in {'customers','customer_verticals'} and d.get('customerPT') is False: boost+=42
    if intent in {'analyst','analysts'} and d.get('analyst') is False: boost+=32
    if intent in {'competition','attack'} and d.get('competitive') is False: boost+=34
    if intent in {'services','partner_program'} and d.get('services') is False: boost+=24
    if intent in {'market','strategy'} and d.get('market') is False: boost+=28
    if intent in {'product'} and d.get('product') is False: boost+=22
    return boost


def query_bucket(row: dict) -> str:
    intent=row.get('intent') or ''
    kind=row.get('kind') or ''
    if kind=='strategic' or intent=='strategic': return 'strategic'
    if intent in {'channel','channel_changes'}: return 'channel'
    if intent in {'ecosystem','partner_capability'} or kind=='competitive-ecosystem': return 'ecosystem'
    if intent in {'customers','customer_verticals'} or kind in {'buyer-followup'}: return 'customers'
    if intent in {'competition','attack'} or kind in {'competitive-pair','buyer-competitive-followup'}: return 'competition'
    if intent in {'analyst','analysts'}: return 'analyst'
    if intent in {'architecture','integration','overlap'} or kind in {'architecture-pair'}: return 'architecture'
    if intent in {'market','strategy','product','services','partner_program','official','procurement','economics','regulation','financial_health','product_lifecycle','delivery','local_signals'}: return 'market'
    return 'other'


def fair_take(rows: list[dict], n: int) -> list[dict]:
    """Round-robin vendors/countries so one gap-heavy vendor cannot consume an entire research bucket."""
    if n<=0 or not rows: return []
    groups=defaultdict(list)
    for r in rows:
        groups[(r.get('vendor') or '__global__',r.get('country') or 'ALL')].append(r)
    for vals in groups.values(): vals.sort(key=lambda r:(-r.get('priority',0),sha(str(NOW.isocalendar().week),r.get('query',''))))
    keys=sorted(groups,key=lambda k:(0 if k[0]=='__global__' else 1,sha(str(NOW.isocalendar().week),*k)))
    out=[]; idx=0
    while len(out)<n and keys:
        k=keys[idx%len(keys)]
        if groups[k]: out.append(groups[k].pop(0))
        if not groups[k]: keys.remove(k); idx=0; continue
        idx+=1
    return out


def stratified_query_selection(rows: list[dict], maxq: int) -> list[dict]:
    mix=DEEP.get('query_mix',{'strategic':0.05,'channel':0.18,'ecosystem':0.14,'customers':0.14,'competition':0.20,'analyst':0.10,'market':0.14,'other':0.05})
    buckets=defaultdict(list)
    for r in rows: buckets[query_bucket(r)].append(r)
    selected=[]; used=set()
    for name,share in mix.items():
        n=max(1,round(maxq*float(share))) if buckets.get(name) else 0
        for r in fair_take(buckets.get(name,[]),n):
            q=r.get('query');
            if q not in used: selected.append(r); used.add(q)
    # Fill unused quota with globally strongest remaining rows, still rotating via hash at equal priority.
    remaining=[r for r in rows if r.get('query') not in used]
    remaining.sort(key=lambda r:(-r.get('priority',0),sha(str(NOW.isocalendar().week),r.get('query',''))))
    selected.extend(remaining[:max(0,maxq-len(selected))])
    return selected[:maxq]


def make_queries() -> list[dict]:
    fixed=[{"query":q,"kind":"strategic","country":"ALL","intent":"strategic","priority":100} for q in CFG.get("strategic_queries",[])]
    coverage=previous_gap_priority(); gapdims=previous_gap_dimensions()
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
                    generated.append({"query":f'"{alias}" {country_word} {term}',"kind":"vendor","vendor":vendor,"country":cc,"intent":intent,"priority":40+lowcov+(20 if intent in {'channel','ecosystem','customers','competition'} else 0)+query_gap_boost(vendor,cc,intent,gapdims)})
            # official-domain targeted search patterns for high-value proof
            domain=CFG.get('vendor_domains',{}).get(vendor)
            if domain:
                for term in ['partners','partner locator','find a partner','partner directory','reseller','VAR','systems integrator','installer','MSP','MSSP','service provider','certified partner','partner awards','customer case study','press release','managed services','Spain','Portugal']:
                    generated.append({"query":f'site:{domain} "{vas[0]}" {country_word} {term}',"kind":"vendor","vendor":vendor,"country":cc,"intent":"official","priority":70+lowcov})
                # Broad partner-universe discovery. Search is intentionally role-rich because
                # vendors use very different channel terminology. Official-domain evidence
                # is preferred; results become relationships only after explicit proof.
                for role_term in ['integrator OR reseller OR VAR','installer OR integrator','MSP OR MSSP OR managed service provider','solution provider OR service provider','certified partner OR gold partner OR platinum partner']:
                    generated.append({"query":f'site:{domain} {country_word} ({role_term}) partner',"kind":"partner-universe","vendor":vendor,"country":cc,"intent":"ecosystem","priority":92+lowcov})
            generated.append({"query":f'"{vas[0]}" {country_word} "partner locator" OR "find a partner"',"kind":"partner-universe","vendor":vendor,"country":cc,"intent":"ecosystem","priority":88+lowcov})
            generated.append({"query":f'"{vas[0]}" {country_word} integrator reseller MSP MSSP certified partner',"kind":"partner-universe","vendor":vendor,"country":cc,"intent":"ecosystem","priority":84+lowcov})
        # analyst/global strategic research
        for analyst in CFG.get('analyst_names',[]):
            generated.append({"query":f'"{vas[0]}" {analyst} 2026 public',"kind":"vendor","vendor":vendor,"country":"ALL","intent":"analyst","priority":52+lowcov})
    # Capability Intelligence: verify Westcon programmes against each active vendor.
    # Weekly/deep runs rotate a compact set; exhaustive runs can cover the full vendor x capability matrix.
    cap_terms=CFG.get('westcon_capability_terms',[])
    cap_cfg=DEEP.get('capability_research',{})
    if cap_cfg.get('enabled',True):
        for vendor in active_vendor_names():
            mapped=CAP.get('vendorApplicability',{}).get(vendor,{})
            # Unverified or generic programme applicability gets the most research budget.
            priority_caps=[]
            for prog in CAP.get('programmes',[]):
                cid=prog.get('id'); status=(mapped.get(cid) or {}).get('status','UNVERIFIED')
                pr=94 if status in {'UNVERIFIED','PROGRAMME_ELIGIBLE','MODEL_ELIGIBLE'} else 67
                priority_caps.append((pr,cid,prog.get('name')))
            priority_caps.sort(reverse=True)
            limit=4 if PROFILE=='daily' else 9 if PROFILE=='deep' else len(priority_caps)
            for pr,cid,label in priority_caps[:limit]:
                q=f'site:westconcomstor.com "{vendor}" "{label}"'
                generated.append({'query':q,'kind':'capability-verification','vendor':vendor,'country':'ALL','intent':'capability','capabilityId':cid,'priority':pr+lowcov//6})
                if PROFILE in {'deep','exhaustive'} and cid in {'tech-insights','3d-lab','tech-xpert','academy','support','professional-services','marketplace'}:
                    generated.append({'query':f'site:westconcomstor.com/es/es "{vendor}" "{label}"','kind':'capability-verification','vendor':vendor,'country':'ES','intent':'capability','capabilityId':cid,'priority':pr+8})
        # Programme-level freshness and scope.
        for term in cap_terms[:20]:
            generated.append({'query':f'site:westconcomstor.com "{term}" Westcon EMEA Europe Spain Portugal','kind':'capability-programme','country':'ALL','intent':'capability','priority':88})

    # Explicit distributor cross-checks: authoritative channel relationships are strategically critical.
    for vendor in active_vendor_names():
        for dist in CFG.get('known_distributors',[]):
            if dist in {'Westcon-Comstor','Comstor'}: continue
            generated.append({"query":f'"{vendor}" "{dist}" Spain distributor authorized linecard',"kind":"vendor","vendor":vendor,"country":"ES","intent":"channel","priority":90})
            generated.append({"query":f'"{vendor}" "{dist}" Portugal distributor authorized linecard',"kind":"vendor","vendor":vendor,"country":"PT","intent":"channel","priority":90})
        # Integrator cross-checks rotate deterministically so weekly runs eventually cover the whole ecosystem.
        ints=list(dict.fromkeys(CFG.get('known_integrators',[])+discovered_integrators()))
        if ints:
            start=int(sha(str(NOW.isocalendar().week),vendor)[:6],16)%len(ints)
            selected=[ints[(start+i)%len(ints)] for i in range(min(8,len(ints)))]
            for integ in selected:
                generated.append({"query":f'"{vendor}" "{integ}" Spain partner case study',"kind":"vendor","vendor":vendor,"country":"ES","intent":"ecosystem","priority":76})
                generated.append({"query":f'"{vendor}" "{integ}" Portugal partner case study',"kind":"vendor","vendor":vendor,"country":"PT","intent":"ecosystem","priority":76})
                for rival in (next((x.get('marketCompetitors',[]) for x in VENDOR_INTEL.get('vendors',[]) if x.get('name')==vendor),[])[:2]):
                    generated.append({"query":f'"{integ}" "{vendor}" "{rival}" partner migration case study',"kind":"competitive-ecosystem","vendor":vendor,"country":"ALL","intent":"attack","priority":82+lowcov})
    # Follow public buyers discovered in procurement. These are market signals, not assumed customers.
    buyer_rows=discovered_buyers()
    if buyer_rows:
        for vendor in active_vendor_names():
            # Rotate across the strongest public-demand buyers so coverage grows over time without exploding query volume.
            start=int(sha('buyer',str(NOW.isocalendar().week),vendor)[:6],16)%len(buyer_rows)
            selected=[buyer_rows[(start+i)%len(buyer_rows)] for i in range(min(3,len(buyer_rows)))]
            rivals=(next((x.get('marketCompetitors',[]) for x in VENDOR_INTEL.get('vendors',[]) if x.get('name')==vendor),[])[:2])
            for b in selected:
                cc=b.get('country') or 'ALL'; country_word='Spain' if cc=='ES' else 'Portugal' if cc=='PT' else 'Iberia'
                generated.append({"query":f'"{vendor}" "{b["name"]}" {country_word} case study contract deployment',"kind":"buyer-followup","vendor":vendor,"country":cc,"intent":"customers","priority":72+max(0,b.get('priority',0)//5)})
                for rival in rivals:
                    generated.append({"query":f'"{rival}" "{b["name"]}" {country_word} case study contract deployment',"kind":"buyer-competitive-followup","vendor":vendor,"country":cc,"intent":"attack","priority":74+max(0,b.get('priority',0)//5)})

    # Pairwise competitive intelligence: displacement, migration, TCO, integrators and customer proof.
    vi={x.get('name'):x for x in VENDOR_INTEL.get('vendors',[])}
    for vendor in active_vendor_names():
        for competitor in (vi.get(vendor,{}).get('marketCompetitors') or [])[:6]:
            generated.append({"query":f'"{vendor}" "{competitor}" Spain replacement migration TCO',"kind":"competitive-pair","vendor":vendor,"country":"ES","intent":"attack","priority":84})
            generated.append({"query":f'"{vendor}" "{competitor}" Portugal replacement migration TCO',"kind":"competitive-pair","vendor":vendor,"country":"PT","intent":"attack","priority":84})
            generated.append({"query":f'"{vendor}" "{competitor}" case study competitive win displacement',"kind":"competitive-pair","vendor":vendor,"country":"ALL","intent":"competition","priority":78})
            generated.append({"query":f'site:{CFG.get("vendor_domains",{}).get(vendor,"example.invalid")} "{vendor}" "{competitor}" integration reference architecture',"kind":"architecture-pair","vendor":vendor,"country":"ALL","intent":"architecture","priority":72})
            generated.append({"query":f'"{vendor}" "{competitor}" control plane overlap platform consolidation',"kind":"architecture-pair","vendor":vendor,"country":"ALL","intent":"overlap","priority":70})
    # Entity-first research avoids reducing every question to a vendor search.
    for dist in CFG.get('known_distributors',[]):
        if dist in {'Westcon-Comstor','Comstor'}: continue
        for cc,country in [('ES','Spain'),('PT','Portugal')]:
            for term in ['official linecard vendors','annual report revenue gross sales','value added services labs financing','market share technology distribution','cloud marketplace managed services']:
                generated.append({'query':f'"{dist}" {country} {term}','kind':'distributor-profile','country':cc,'intent':'channel','entity':dist,'priority':86})
    
    profile_universe=list(dict.fromkeys(CFG.get('known_integrators',[])+discovered_integrators(300)))
    profile_limit=48 if PROFILE=='daily' else 120 if PROFILE=='deep' else min(300,len(profile_universe))
    if profile_universe:
        offset=int(sha('integrator-profiles',str(NOW.isocalendar().week))[:6],16)%len(profile_universe)
        profile_universe=[profile_universe[(offset+i)%len(profile_universe)] for i in range(min(profile_limit,len(profile_universe)))]
    for integ in profile_universe:
        for cc,country in [('ES','Spain'),('PT','Portugal')]:
            for term in ['certifications vendor specializations','technology partners portfolio','customer case study','annual revenue employees','distributor preferred procurement']:
                generated.append({'query':f'"{integ}" {country} {term}','kind':'integrator-profile','country':cc,'intent':'ecosystem','entity':integ,'priority':82})
    # Dedup then deterministic weighted rotation.
    ded={}
    for r in fixed+generated:
        ded[r['query']]=max(ded.get(r['query'],r),r,key=lambda x:x.get('priority',0)) if r['query'] in ded else r
    rows=list(ded.values()); learning=load_json_state(LEARNING_OUT, {})
    for row in rows: row['priority']=int(row.get('priority',0))+adaptive_bonus(row,learning)
    week=NOW.isocalendar().week
    rows.sort(key=lambda r:(-r.get('priority',0),sha(str(week),r['query'])))
    maxq=int(BUDGETS.get('query_limit_public',CFG.get('no_brave_rotation_max_queries',180)))
    # Keep an explicit exploration slice so high-yield known strategies never starve new dimensions.
    share=float(DEEP.get('adaptive_learning',{}).get('minimum_exploration_share',.12)); explore_n=max(1,round(maxq*share))
    unseen=[r for r in rows if not any(k.endswith('|'.join([r.get('kind','other'),r.get('intent','other'),r.get('country','ALL')])) for k in learning.get('strategies',{}))]
    unseen.sort(key=lambda r:sha('explore',str(NOW.isocalendar().week),r.get('query','')))
    explore=unseen[:explore_n]; explore_q={x['query'] for x in explore}
    exploit=stratified_query_selection([r for r in rows if r['query'] not in explore_q],maxq-len(explore))
    return (explore+exploit)[:maxq]


def capability_candidates(evidence: list[dict]) -> list[dict]:
    """Extract vendor x Westcon-capability evidence from official Westcon pages.

    Discovery results remain signals; the UI only auto-promotes official Westcon evidence.
    """
    programmes=CAP.get('programmes',[])
    aliases={p['id']:[p.get('name','')]+({
        'tech-insights':['Tech Insights','assessment'],
        '3d-lab':['3D Lab','3DLab'],
        'tech-xpert':['Tech Xpert','Tech ConneX'],
        'intelligent-demand':['Intelligent Demand'],
        'academy':['Academy','SkillBoost','training'],
        'professional-services':['professional services','installation','configuration','project management'],
        'support':['Westcon Care','Westcon Assist','support services','Level 1','Level 2 support'],
        'supply-chain':['supply chain','staging','reverse logistics','shipment'],
        'flex':['Flex','flexible payment'],
        'marketplace':['AWS Marketplace','cloud marketplace'],
        'lifecycle':['lifecycle','renewal','refresh'],
        'gscs':['GSCS','Global Supply Chain Solutions'],
        'marketing-local':['Marketing as a Service','campaign','Intelligent Demand'],
        'local-presales':['Solution Architect','presales','pre-sales','PoC','PoV'],
        'vsm':['Vendor Success Manager','VSM'],
        'psm':['Partner Success Manager','PSM']}.get(p['id'],[])) for p in programmes}
    out=[]; seen=set()
    for e in evidence:
        if host(e.get('url','')) not in {'westconcomstor.com','academy.westconcomstor.com'} and not host(e.get('url','')).endswith('.westconcomstor.com'):
            continue
        text=norm(f"{e.get('title','')} {e.get('summary','')} {e.get('snippet','')} {e.get('query','')}")
        vendor=e.get('vendor')
        if not vendor:
            for vn in active_vendor_names():
                if norm(vn) in text: vendor=vn; break
        if not vendor or vendor not in active_vendor_names(): continue
        for cid,terms in aliases.items():
            if any(norm(t) and norm(t) in text for t in terms):
                key=(vendor,cid,e.get('url'))
                if key in seen: continue
                seen.add(key)
                official=e.get('sourceTier')=='official-company'
                out.append({'vendor':vendor,'capabilityId':cid,'status':'VERIFIED_PUBLIC_DISCOVERED' if official else 'DISCOVERY','scope':e.get('scope'),'country':e.get('country'),'confidence':min(98,int(e.get('confidence',50))+ (8 if official else 0)),'title':e.get('title'),'url':e.get('url'),'date':e.get('date'),'source':e.get('source'),'evidenceId':e.get('id')})
    return sorted(out,key=lambda x:(x['vendor'],x['capabilityId'],-x['confidence']))

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
        'published':x.get('published'),'engine':x.get('engine'),'confidence':confidence_for(tier,scope,x.get('engine',''),direct),
        'collectedAt':NOW.isoformat(),'validationState':'primary/public source' if tier in {'regulator','public-open-data','official-company','analyst-public'} else 'discovery; validate before executive use',
        'buyer':x.get('buyer'),'winner':x.get('winner'),'winners':x.get('winners') or ([x.get('winner')] if x.get('winner') else []),
        'contractId':x.get('contractId'),'status':x.get('status'),'cpv':x.get('cpv') or [],'estimatedValue':x.get('estimatedValue'),'awardedValue':x.get('awardedValue'),'currency':x.get('currency'),
        'awardDate':x.get('awardDate'),'technologyMatches':x.get('technologyMatches') or [],'sector':x.get('sector'),'object':x.get('object'),'procurementAttribution':x.get('procurementAttribution'),'sourceKind':x.get('sourceKind')
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


def partner_name_candidates_from_evidence(e: dict) -> list[str]:
    """Conservatively extract new partner names from explicit relationship text.

    This never promotes a relationship on its own: integrator_candidates still
    requires a tracked Westcon vendor, partner/integrator context and geography.
    The heuristic is purposely narrow to avoid turning generic prose into firms.
    """
    text=clean(f"{e.get('title','')} {e.get('snippet','')}")
    if not text or not any(x in norm(text) for x in ['partner','integrator','reseller','msp','mssp','solution provider','service provider','instalador','integrador','parceiro']):
        return []
    vendor_aliases={norm(a) for v in tracked_names() for a in aliases_for(v)[:3]}
    stop={'spain','espana','portugal','iberia','partners','partner','customer','customers','case study','home','solutions','services','network','security','cloud'}
    candidates=[]
    patterns=[
        r'^([^|–—:\-]{2,80})\s*(?:\||–|—|:)\s*[^|]{0,100}\b(?:partner|integrator|reseller|msp|mssp)\b',
        r'\b(?:names?|named|recognizes?|recognised|recognized|premia|premiado|premiada|award(?:s|ed)?|wins?)\s+([A-ZÁÉÍÓÚÑÇ][A-Za-zÀ-ÿ0-9&+. ]{2,70}?)\s+(?:as|como|the|a|partner|integrator|reseller)',
        r'\b(?:partner|integrator|reseller|msp|mssp|parceiro|integrador)\s+(?:is|es|é|:)?\s*([A-ZÁÉÍÓÚÑÇ][A-Za-zÀ-ÿ0-9&+. ]{2,70})(?:[,.|–—]|$)'
    ]
    for pat in patterns:
        for m in re.finditer(pat,text,re.I if pat.startswith('^') else 0):
            name=clean(m.group(1)).strip(' -–—:|,.')
            n=norm(name)
            if not name or len(name)<3 or len(name)>80 or n in stop or n in vendor_aliases: continue
            if any(term in n for term in ['find a partner','partner locator','case study','customer story','press release']): continue
            if name not in candidates: candidates.append(name)
    return candidates[:6]


def _integrator_signal_dimensions(text: str, evidence: dict) -> dict:
    """Extract only explicitly stated public capabilities from partner evidence.

    This enriches the user-facing intelligence without turning keyword affinity into
    a partnership claim. Partnership is still established separately by the existing
    relation-proof rules. The terms below only populate descriptive dimensions when
    they actually occur in the source text.
    """
    nt = norm(text)
    services=[]; capabilities=[]; specializations=[]; verticals=[]; public_cases=[]

    service_terms=[
        (("managed service","servicios gestionados","managed security"), "Managed services"),
        (("professional service","servicios profesionales"), "Professional services"),
        (("consulting","consultoria","consultoría"), "Consulting"),
        (("implementation","implementacion","implementación","deployment","despliegue"), "Implementation / deployment"),
        (("systems integration","system integrator","integracion de sistemas","integración de sistemas"), "Systems integration"),
        (("support service","support services","soporte"), "Support services"),
    ]
    capability_terms=[
        (("mssp","managed security service provider"), "MSSP"),
        (("managed service provider",), "MSP"),
        (("security operations center","security operations centre"," soc ","centro de operaciones de seguridad"), "SOC"),
        (("network operations center","network operations centre"," noc ","centro de operaciones de red"), "NOC"),
        (("24x7","24/7","24 x 7"), "24x7 operations"),
    ]
    specialization_terms=[
        (("zero trust","confianza cero"), "Zero Trust"),
        (("sase",), "SASE"), (("sse","security service edge"), "SSE"),
        (("private 5g","private mobile network","red privada 5g","redes privadas 5g"), "Private 4G/5G"),
        (("ot security","industrial cybersecurity","ciberseguridad ot","ciberseguridad industrial","ics security"), "OT / ICS security"),
        (("identity","iam","identity and access"), "Identity & Access"),
        (("threat intelligence","inteligencia de amenazas"), "Threat intelligence"),
        (("ctem","continuous threat exposure"), "CTEM / Exposure validation"),
        (("application security","web application security","api security","seguridad de aplicaciones"), "Application & API security"),
        (("microsegmentation","microsegmentacion","microsegmentación"), "Microsegmentation"),
        (("ddos",), "DDoS protection"),
        (("observability","observabilidad"), "Observability"),
        (("microsoft teams","direct routing"), "Microsoft Teams / Direct Routing"),
        (("contact center","contact centre","centro de contacto"), "Contact Center"),
        (("automation","automatizacion","automatización","rpa"), "Automation"),
    ]
    vertical_terms=[
        (("public sector","sector publico","sector público","government"), "Public sector"),
        (("healthcare","hospital","salud"), "Healthcare"),
        (("financial services","banking","banca"), "Financial services"),
        (("manufacturing","fabricacion","fabricación","factory","industrial"), "Manufacturing / Industrial"),
        (("energy","utilities","energia","energía"), "Energy & Utilities"),
        (("retail",), "Retail"),
        (("telecom","service provider","operador"), "Telecommunications"),
        (("education","university","universidad"), "Education"),
        (("transport","logistics","logistica","logística","port","puerto"), "Transport & Logistics"),
        (("defence","defense","defensa"), "Defense"),
    ]
    for terms,label in service_terms:
        if any(t in nt for t in terms): services.append(label)
    for terms,label in capability_terms:
        if any(t in nt for t in terms): capabilities.append(label)
    for terms,label in specialization_terms:
        if any(t in nt for t in terms): specializations.append(label)
    for terms,label in vertical_terms:
        if any(t in nt for t in terms): verticals.append(label)

    buyer=clean(evidence.get('buyer',''))
    if buyer and evidence.get('evidenceType') in {'customer','procurement'}:
        public_cases.append(buyer)
    return {
        'services': list(dict.fromkeys(services)),
        'capabilities': list(dict.fromkeys(capabilities)),
        'specializations': list(dict.fromkeys(specializations)),
        'verticals': list(dict.fromkeys(verticals)),
        'public_cases': list(dict.fromkeys(public_cases)),
    }


def integrator_candidates(evidence: list[dict]) -> list[dict]:
    names=list(dict.fromkeys(CFG.get('known_integrators',[])+discovered_integrators(300))); vendors=tracked_names(); rows={}
    for e in evidence:
        text=norm(f"{e.get('title','')} {e.get('snippet','')} {e.get('query','')} {e.get('winner','')}")
        matched_vendors=[v for v in vendors if any(norm(a) in text for a in aliases_for(v)[:3])]
        if e.get('vendor') and e['vendor'] not in matched_vendors: matched_vendors.append(e['vendor'])
        matched=[n for n in names if norm(n) in text]
        for discovered_name in partner_name_candidates_from_evidence(e):
            if discovered_name not in matched: matched.append(discovered_name)
        if e.get('winner') and e['winner'] and e['winner'] not in matched: matched.append(e['winner'])
        if not matched_vendors or not matched: continue
        if e.get('evidenceType') not in {'integrator','customer','partner-program','services','procurement'} and not any(x in text for x in ['partner','integrator','mssp','implementation','winner','adjudicat']): continue
        countries=countries_from_scope(e.get('scope','')) or ([e['country']] if e.get('country') in {'ES','PT'} else [])
        for cc in countries:
            for v in matched_vendors:
                for name in matched[:4]:
                    if not clean(name): continue
                    key=(v,cc,clean(name))
                    nt=norm(text)
                    role='MSSP' if 'mssp' in nt else 'MSP' if 'managed service provider' in nt or re.search(r'\bmsp\b',nt) else 'Reseller / VAR' if 'reseller' in nt or re.search(r'\bvar\b',nt) else 'Instalador / Integrador' if 'installer' in nt or 'instalador' in nt else 'Integrador / Partner'
                    explicit_partner = e.get('sourceTier') in {'official-company','public-open-data'} or e.get('evidenceType') in {'partner-program','integrator'}
                    proof_type='official-partner-signal' if explicit_partner else 'public-partner-signal'
                    dims=_integrator_signal_dimensions(text,e)
                    row=rows.setdefault(key,{'vendor':v,'country':cc,'name':clean(name),'role':role,'status':'candidate-public-signal','proofType':proof_type,'confidence':0,'evidence':[],'url':e.get('url'),'source':e.get('source'),'signal':e.get('title') or e.get('snippet'),'services':[],'capabilities':[],'specializations':[],'verticals':[],'public_cases':[]})
                    for dim in ('services','capabilities','specializations','verticals','public_cases'):
                        row[dim]=list(dict.fromkeys((row.get(dim) or [])+(dims.get(dim) or [])))
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


def discovery_plan(queries: list[dict]) -> list[tuple[dict,str]]:
    budgets={'news':int(BUDGETS.get('news_queries_max',180)),'gdelt':int(BUDGETS.get('gdelt_queries_max',150)),'arquivo':int(BUDGETS.get('arquivo_queries_max',40))}
    counts=Counter(); plan=[]
    for q in queries:
        if counts['news']<budgets['news']: plan.append((q,'news')); counts['news']+=1
        if counts['gdelt']<budgets['gdelt'] and (query_bucket(q) in {'channel','ecosystem','customers','competition','market','architecture'} or q.get('kind')=='strategic'): plan.append((q,'gdelt')); counts['gdelt']+=1
        if counts['arquivo']<budgets['arquivo'] and q.get('country')=='PT' and query_bucket(q) in {'channel','ecosystem','customers'}: plan.append((q,'arquivo')); counts['arquivo']+=1
    return plan


def result_reward(rows: list[dict], qrow: dict) -> float:
    if not rows: return 0.0
    cfg=DEEP.get('adaptive_learning',{}); w=cfg.get('reward_weights',{}); reward=0.0
    domains=set()
    for row in rows:
        url=row.get('url',''); tier=source_tier(url); txt=f"{row.get('title','')} {row.get('snippet','')}"
        domains.add(host(url))
        reward += (w.get('primary_source',.32) if tier in {'official-company','analyst-public','regulator','public-open-data'} else 0)
        reward += (w.get('iberia_precision',.22) if infer_scope(txt,qrow.get('country')) in {'Spain','Portugal','Spain / Portugal','Iberia'} else 0)
        reward += (w.get('numeric_claim',.14) if re.search(r'\b\d+(?:[.,]\d+)?\s?(?:%|billion|million|bn|m|€|\$)',txt,re.I) else 0)
    reward /= max(1,len(rows)); reward += min(.15,max(0,len(domains)-1)*w.get('corroboration',.09))
    return round(reward,4)


def run_discovery_batches(queries: list[dict]) -> tuple[list[dict],dict]:
    """Bounded, resumable search. One broken engine never aborts the other engines."""
    plan=discovery_plan(queries); run_key=f'{TODAY}|{PROFILE}'; saved=load_json_state(QUEUE_OUT,{})
    completed=set(saved.get('completed',[])) if saved.get('runKey')==run_key else set()
    raw=list(saved.get('partialEvidence',[])) if saved.get('runKey')==run_key else []
    learning=load_json_state(LEARNING_OUT,{'version':1,'totalTrials':0,'strategies':{},'sources':{}})
    batch_size=int(BUDGETS.get('batch_size',DEEP.get('resilience',{}).get('batch_size',24))); fail_limit=int(DEEP.get('resilience',{}).get('circuit_breaker_failures',6)); cooldown=int(DEEP.get('resilience',{}).get('circuit_breaker_cooldown_batches',3))
    circuit={}; failures=Counter(); processed=0
    funcs={'news':search_google_news,'gdelt':search_gdelt,'arquivo':search_arquivo}
    pending=[(q,e,sha(e,q.get('query',''))) for q,e in plan if sha(e,q.get('query','')) not in completed]
    stage_seconds=max(30,int(BUDGETS.get('discovery_stage_seconds',max(60,MAX_RUNTIME_SECONDS*.3))))
    stage_deadline=min(DEADLINE-int(BUDGETS.get('finalize_reserve_seconds',180)),time.monotonic()+stage_seconds)
    for batch_no,start in enumerate(range(0,len(pending),batch_size),1):
        if should_stop(int(BUDGETS.get('finalize_reserve_seconds',180))) or time.monotonic()>=stage_deadline:
            print(f'discovery paused safely with {seconds_left():.0f}s left; checkpoint will be resumed')
            break
        chunk=pending[start:start+batch_size]; runnable=[]
        for q,e,key in chunk:
            if circuit.get(e,0)>batch_no: continue
            runnable.append((q,e,key))
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures={ex.submit(funcs[e],q):(q,e,key) for q,e,key in runnable}
            for fut in as_completed(futures):
                q,e,key=futures[fut]; processed+=1; completed.add(key)
                try: rows=fut.result(); failures[e]=0
                except Exception as exc:
                    rows=[]; failures[e]+=1; trace_error(f'discovery-{e}',exc,source=q.get('query',''))
                    if failures[e]>=fail_limit: circuit[e]=batch_no+cooldown; failures[e]=0; print(f'{e} circuit open until batch {circuit[e]}')
                for row in rows: raw.append(to_evidence(row,q))
                lk=learning_key(q,e); stat=learning.setdefault('strategies',{}).setdefault(lk,{'trials':0,'reward':0.0,'hits':0})
                stat['trials']+=1; stat['reward']=round(float(stat.get('reward',0))*float(DEEP.get('adaptive_learning',{}).get('decay_per_run',.985))+result_reward(rows,q),4); stat['hits']+=int(bool(rows)); stat['updatedAt']=NOW.isoformat(); learning['totalTrials']=int(learning.get('totalTrials',0))+1
                for row in rows:
                    h=host(row.get('url',''))
                    if h:
                        ss=learning.setdefault('sources',{}).setdefault(h,{'seen':0,'primaryHits':0}); ss['seen']+=1; ss['primaryHits']+=int(source_tier(row.get('url','')) in {'official-company','analyst-public','regulator','public-open-data'}); ss['updatedAt']=NOW.isoformat()
        checkpoint={'version':1,'runKey':run_key,'profile':PROFILE,'updatedAt':NOW.isoformat(),'planned':len(plan),'completed':sorted(completed),'partialEvidence':raw,'circuits':circuit}
        atomic_json(QUEUE_OUT,checkpoint); atomic_json(LEARNING_OUT,learning)
        print(f'discovery batch {batch_no}: {len(completed)}/{len(plan)} tasks · {len(raw)} signals · {seconds_left():.0f}s left',flush=True)
    complete=len(completed)>=len(plan)
    atomic_json(QUEUE_OUT,{'version':2,'runKey':run_key,'profile':PROFILE,'updatedAt':NOW.isoformat(),'planned':len(plan),'completed':sorted(completed),'partialEvidence':[] if complete else raw,'complete':complete,'pending':max(0,len(plan)-len(completed))})
    return raw,{'plannedTasks':len(plan),'processedTasks':processed,'completedTasks':len(completed),'pendingTasks':max(0,len(plan)-len(completed)),'partialRun':not complete,'resumedTasks':len(plan)-len(pending),'circuits':circuit,'learningStrategies':len(learning.get('strategies',{}))}


# ----------------------------- Main -----------------------------

def main() -> None:
    prev=load_previous_payload()
    queries=make_queries()
    evidence=[dict(e,curated=True) for e in CURATED.get('evidence',[])]
    evidence.extend(dict(e,curated=True,realityVerified=True) for e in MARKET_REALITY.get('facts',[]))
    evidence.extend(carryover_evidence(prev))
    resilience_stats={'plannedTasks':0,'processedTasks':0,'pendingTasks':0,'partialRun':False}

    row,started=stage_start('adaptive-discovery')
    try:
        discovered,resilience_stats=run_discovery_batches(queries)
        evidence.extend(discovered)
        stage_end(row,started,'partial' if resilience_stats.get('partialRun') else 'completed',signals=len(discovered),**resilience_stats)
    except Exception as exc:
        trace_error('adaptive-discovery',exc)
        stage_end(row,started,'degraded',signals=0)

    row,started=stage_start('official-partner-portal-seeds')
    if should_stop(240):
        stage_end(row,started,'deferred')
    else:
        try:
            found=official_portal_seed_evidence()
            for x in found:
                evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'partner-universe','country':x.get('country'),'intent':'ecosystem','query':f"official partner portal seed {x.get('sourceEntity','')}"}))
            stage_end(row,started,'completed',signals=len(found))
        except Exception as exc:
            trace_error('official-partner-portal-seeds',exc); stage_end(row,started,'degraded')

    row,started=stage_start('official-vendor-crawl')
    if should_stop(300):
        stage_end(row,started,'deferred')
    else:
        try:
            found=official_sitemap_evidence([v for v in tracked_names() if CFG.get('vendor_domains',{}).get(v)])
            for x in found: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-vendor-crawl','country':x.get('country'),'query':'official vendor sitemap crawl'}))
            stage_end(row,started,'completed',signals=len(found))
        except Exception as exc:
            trace_error('official-vendor-crawl',exc);stage_end(row,started,'degraded')

    row,started=stage_start('commoncrawl-revalidation')
    cc_budget=int(BUDGETS.get('commoncrawl_pages_max',0))
    if cc_budget<=0 or should_stop(300):
        stage_end(row,started,'deferred')
    else:
        try:
            found=commoncrawl_official_evidence([v for v in tracked_names() if CFG.get('vendor_domains',{}).get(v)],cc_budget)
            for x in found: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-commoncrawl-discovery','country':x.get('country'),'query':'Common Crawl URL discovery + live official validation'}))
            stage_end(row,started,'completed',signals=len(found))
        except Exception as exc:
            trace_error('commoncrawl-revalidation',exc);stage_end(row,started,'degraded')

    row,started=stage_start('ecosystem-official-crawl')
    if should_stop(360):
        stage_end(row,started,'deferred')
    else:
        try:
            budget=int(BUDGETS.get('ecosystem_sitemap_pages_max',0));dist_budget=budget//2;int_budget=budget-dist_budget
            dist=official_entity_sitemap_evidence(CFG.get('distributor_domains',{}),'distributor',dist_budget)
            integ=[] if should_stop(300) else official_entity_sitemap_evidence(CFG.get('integrator_domains',{}),'integrator',int_budget)
            for x in dist: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-distributor-crawl','country':x.get('country'),'query':f"official distributor crawl {x.get('sourceEntity','')}"}))
            for x in integ: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'official-integrator-crawl','country':x.get('country'),'query':f"official integrator crawl {x.get('sourceEntity','')}"}))
            stage_end(row,started,'partial' if not integ and int_budget else 'completed',distributorSignals=len(dist),integratorSignals=len(integ))
        except Exception as exc:
            trace_error('ecosystem-official-crawl',exc);stage_end(row,started,'degraded')

    row,started=stage_start('analyst-public-crawl')
    analyst_budget=int(BUDGETS.get('analyst_sitemap_pages_max',0)) if PROFILE in {'deep','exhaustive'} else 0
    if analyst_budget<=0 or should_stop(300):
        stage_end(row,started,'deferred')
    else:
        try:
            found=official_analyst_sitemap_evidence(analyst_budget)
            for x in found: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'analyst-official-crawl','country':'ALL','query':'public analyst sitemap crawl'}))
            stage_end(row,started,'completed',signals=len(found))
        except Exception as exc:
            trace_error('analyst-public-crawl',exc);stage_end(row,started,'degraded')

    procurement=[]
    row,started=stage_start('public-procurement')
    if should_stop(300):
        stage_end(row,started,'deferred')
    else:
        cov=previous_gap_priority();ranked=sorted(active_vendor_names(),key=lambda v:(cov.get(v,0),v))
        ted_limit=int(BUDGETS.get('ted_vendor_limit',len(ranked)));ted_vendors=rotate_rows(ranked,ted_limit,'ted-vendors')
        try:
            with ThreadPoolExecutor(max_workers=min(WORKERS,8)) as ex:
                futs={ex.submit(ted_search,v,c):(v,c) for v in ted_vendors for c in ('ES','PT')}
                for fut in as_completed(futs):
                    try: procurement.extend(fut.result())
                    except Exception as exc: trace_error('public-procurement-ted',exc,source=str(futs[fut]))
            if BUDGETS.get('full_procurement',False) and not should_stop(420):
                try: procurement.extend(official_spain_procurement_rows(active_vendor_names()))
                except Exception as exc: trace_error('public-procurement-placsp',exc,'PLACSP')
            if BUDGETS.get('full_procurement',False) and not should_stop(300):
                try: procurement.extend(dados_gov_pt_contract_rows(active_vendor_names()))
                except Exception as exc: trace_error('public-procurement-dados-pt',exc,'dados.gov.pt')
            for x in procurement: evidence.append(to_evidence(x,{'vendor':x.get('vendor'),'kind':'procurement','country':x.get('country'),'query':'public procurement'}))
            stage_end(row,started,'completed' if not should_stop(240) else 'partial',signals=len(procurement))
        except Exception as exc:
            trace_error('public-procurement',exc);stage_end(row,started,'degraded',signals=len(procurement))

    row,started=stage_start('corroborate-and-publish')
    evidence=corroborate(dedupe_evidence(evidence))
    all_channels=merge_channel_signals(CURATED.get('channelSignals',[]),relation_candidates(evidence))
    conflicts=detect_conflicts(evidence,all_channels);channels,ended_channels=resolve_channel_lifecycle(all_channels,conflicts)
    seeded_integrators=[dict(x,status='curated-public') for x in ECOSYSTEM.get('integrators',[]) if x.get('vendor')!='Juniper Networks']
    integrators=merge_integrators(seeded_integrators,integrator_candidates(evidence))
    seeded_customers=[dict(x,status='curated-public') for x in ECOSYSTEM.get('customers',[]) if x.get('vendor')!='Juniper Networks']
    customers=merge_customers(seeded_customers,procurement_customer_candidates(evidence))
    analysts=analyst_candidates(evidence);capability_signals=capability_candidates(evidence)
    coverage=vendor_coverage(evidence,channels,integrators,customers);procurement_market=procurement_market_aggregate(evidence)
    dynamic_entities=dynamic_entity_catalog(channels,integrators,procurement_market)
    changes=compute_changes(prev,channels,integrators,customers,coverage,procurement_market,ended_channels)
    stage_end(row,started,'completed',evidence=len(evidence),changes=len(changes))
    partial=bool(resilience_stats.get('partialRun') or RUN_ERRORS or any(x.get('status') in {'partial','degraded','deferred'} for x in RUN_STAGES))
    outcome='partial-recoverable' if partial else 'complete'
    engines=['official partner portal seeds','Google News RSS','GDELT DOC 2.0','Arquivo.pt','official vendor sitemaps','Common Crawl URL discovery + live validation','official distributor/integrator sitemaps','public analyst pages','TED Search API','PLACSP open data','dados.gov.pt public datasets']
    payload={
        'generatedAt':NOW.isoformat(),'runId':RUN_ID,'runOutcome':outcome,'profile':PROFILE,'mode':'bounded-adaptive-intelligence-graph-v11.1','queryCount':len(queries),'freeOnly':True,
        'notice':'Solo inteligencia pública externa y gratuita, sin claves ni suscripciones. Cada ejecución está acotada por tiempo: publica lo válido, conserva pendientes y nunca convierte discovery o ausencia de datos en un hecho.',
        'researchEngines':engines,'evidence':evidence,'capabilitySignals':capability_signals,'channelSignals':channels,'channelHistorySignals':ended_channels,'integratorSignals':integrators,'customerSignals':customers,'analystSignals':analysts,'procurementMarket':procurement_market,'coverage':coverage,'gaps':research_gaps(coverage),'conflicts':conflicts,'changes':changes,
        'derived':{'evidenceCount':len(evidence),'officialOrAnalystCount':sum(1 for e in evidence if e.get('sourceTier') in {'official-company','regulator','public-open-data','analyst-public'}),'channelSignalCount':len(channels),'endedChannelSignalCount':len(ended_channels),'integratorSignalCount':len(integrators),'customerSignalCount':len(customers),'procurementSignalCount':sum(1 for e in evidence if e.get('evidenceType')=='procurement'),'procurementMarketBuckets':len(procurement_market),'knownProcurementValueEUR':round(sum(x.get('knownValueEUR',0) for x in procurement_market),2),'analystSignalCount':len(analysts),'capabilitySignalCount':len(capability_signals),'conflictCount':len(conflicts),'changeCount':len(changes),'resilience':resilience_stats,'statistics':signal_stats(evidence),'runStages':RUN_STAGES,'runErrorCount':len(RUN_ERRORS)}
    }
    atomic_json(OUT,payload);atomic_json(CHANGES_OUT,{'generatedAt':NOW.isoformat(),'runId':RUN_ID,'profile':PROFILE,'changes':changes,'conflicts':conflicts});atomic_json(DYNAMIC_ENTITIES_OUT,dynamic_entities)
    atomic_json(STATUS_OUT,{'generatedAt':NOW.isoformat(),'runId':RUN_ID,'outcome':outcome,'profile':PROFILE,'freeOnly':True,'queryCount':len(queries),'budgets':BUDGETS,'resilience':resilience_stats,'coverageAverage':round(sum(x['coverage'] for x in coverage)/max(1,len(coverage)),1),'vendorsWithCoverage70':sum(1 for x in coverage if x['coverage']>=70),'gapsP0':sum(1 for x in research_gaps(coverage) if x['priority']=='P0'),'errorCount':len(RUN_ERRORS),'engines':engines})
    write_light_history(payload,changes)
    write_run_diagnostics(outcome,evidenceCount=len(evidence),pendingTasks=resilience_stats.get('pendingTasks',0))
    print(f"Research v11.1/{PROFILE} [{RUN_ID}] {outcome}: {len(evidence)} evidence, {len(channels)} channel, {len(integrators)} integrators, {len(customers)} customers, {len(queries)} planned queries, {len(changes)} changes",flush=True)


if __name__=='__main__':
    try:
        main()
    except BaseException as exc:
        trace_error('fatal',exc,recoverable=False)
        try: write_run_diagnostics('failed-last-good-preserved')
        except Exception: pass
        raise
