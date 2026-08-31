from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urldefrag

import requests

from ..enrichment import merge_field
from ..model import canonical
from .planner import plan

ROOT = Path(__file__).resolve().parents[2]
VERSION = "3.20.0"
UA = "Westcon-Iberia-Decision-Intelligence/3.20 (+public-research; respectful; contact=repository-owner)"

ROUTES = {
    "official": ["/", "/about", "/empresa", "/sobre-nos", "/quem-somos", "/sitemap.xml"],
    "partners": ["/partners", "/technology-partners", "/parceiros", "/socios", "/alianzas", "/vendors", "/fabricantes", "/marcas", "/portfolio", "/line-card"],
    "services": ["/services", "/servicios", "/servicos", "/solutions", "/soluciones", "/solucoes", "/cybersecurity", "/cloud"],
    "cases": ["/customers", "/clientes", "/case-studies", "/casos", "/projects", "/proyectos", "/industrias", "/industries", "/setores"],
    "careers": ["/careers", "/jobs", "/empleo", "/talent", "/oportunidades", "/carreiras", "/emprego"],
    "technology": ["/technology", "/tecnologia", "/solutions", "/soluciones", "/services", "/servicios"],
    "financial": ["/investors", "/investor-relations", "/annual-report", "/resultados", "/relatorio-e-contas"],
    "news": ["/news", "/noticias", "/insights", "/press", "/actualidad"],
    "analyst": ["/analyst", "/reports", "/resources"],
    "signals": ["/news", "/careers", "/projects"],
    "procurement": ["/contratacion", "/procurement"],
}

PAGE_HINT = re.compile(r"partner|vendor|fabric|marca|portfolio|line.?card|service|servic|solu|career|job|emple|emprego|talent|case|caso|customer|client|project|industr|sector|cloud|security|network|soc|noc", re.I)

CAPABILITY_TERMS = {
    "SOC": ["security operations center", "security operation center", "cybersoc", " soc "],
    "NOC": ["network operations center", " noc "],
    "MSSP": ["mssp", "managed security service"],
    "Managed Services": ["managed services", "servicios gestionados", "serviços geridos"],
    "Cloud": ["cloud", "nube"],
    "Cybersecurity": ["cybersecurity", "ciberseguridad", "cibersegurança"],
    "Networking": ["networking", "redes", "conectividad", "connectivity"],
    "Data Center": ["data center", "datacenter"],
    "Observability": ["observability", "observabilidad"],
    "Identity & Access": ["identity", "identidad", "iam", "pam"],
    "Incident Response": ["incident response", "respuesta a incidentes", "resposta a incidentes", "dfir"],
    "Threat Intelligence": ["threat intelligence", "inteligencia de amenazas", "inteligência de ameaças"],
}

SERVICE_TERMS = {
    "Consultoría": ["consulting services", "consultoría", "consultoria"],
    "Servicios profesionales": ["professional services", "servicios profesionales", "serviços profissionais"],
    "Servicios gestionados": ["managed services", "servicios gestionados", "serviços geridos"],
    "Implementación / integración": ["implementation", "implementación", "implementação", "integration", "integración", "integração"],
    "Soporte": ["support services", "soporte", "suporte"],
    "Cloud gestionado": ["public cloud management", "managed cloud", "cloud management"],
    "Security Operations": ["security operations", "cybersoc", "soc as a service", "socaaS"],
}

JOB_PROFILE_TERMS = {
    "Solutions Architect": ["solutions architect", "solution architect", "arquitecto de soluciones", "arquiteto de soluções"],
    "Security Engineer / Analyst": ["security engineer", "security analyst", "analista de seguridad", "cybersecurity", "ciberseguridad"],
    "Cloud Engineer / Architect": ["cloud engineer", "cloud architect", "arquitecto cloud", "arquiteto cloud"],
    "Network Engineer": ["network engineer", "systems engineer - networking", "ingeniero de redes", "engenheiro de redes"],
    "DevOps / Platform": ["devops", "platform engineer"],
    "Presales": ["presales", "pre-sales", "preventa", "pré-venda"],
    "SOC / Detection & Response": ["cybersoc", "soc analyst", "detection and response", "incident response"],
    "Data / AI": ["data engineer", "data architect", "data & ai", "machine learning", "artificial intelligence"],
}

VERTICAL_TERMS = {
    "Sector público": ["public sector", "administraciones públicas", "administrações públicas", "government"],
    "Sanidad": ["healthcare", "sanidad", "saúde", "hospital"],
    "Servicios financieros": ["financial services", "banca", "banking", "insurance", "seguros"],
    "Telecomunicaciones": ["telecommunications", "telecomunicaciones", "telecomunicações", "telco"],
    "Industria": ["manufacturing", "industria", "industry 4.0"],
    "Retail": ["retail", "gran consumo", "consumer goods"],
    "Energía": ["energy", "energía", "energia", "utilities"],
    "Educación": ["education", "educación", "educação", "universit"],
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)
            if self._in_title:
                self.title_parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.parts)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts)[:220]


def _load(rel: str, default: Any) -> Any:
    p = ROOT / rel
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(rel: str, obj: Any) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_index(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out = {}
    for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures"):
        for row in data.get(section) or []:
            out[(section, canonical(row.get("name")))] = row
    return out


def _official_urls(row: dict[str, Any]) -> list[str]:
    urls = []
    def add(ev: Any) -> None:
        if not isinstance(ev, dict):
            return
        url = str(ev.get("url") or "")
        if not url.startswith("http"):
            return
        grade = str(ev.get("source_grade") or "")
        if ev.get("official") is True or grade.startswith("A") or "official" in str(ev.get("source_type") or "").lower():
            urls.append(url)
    for ev in row.get("evidence") or []:
        add(ev)
    for field in (row.get("fields") or {}).values():
        for ev in field.get("evidence") or []:
            add(ev)
        for item in field.get("items") or []:
            if isinstance(item, dict):
                for ev in item.get("evidence") or []:
                    add(ev)
    # one URL per host is enough to discover the official site
    hosts = set(); result = []
    for url in urls:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if host and host not in hosts:
            hosts.add(host); result.append(url)
    return result[:3]


def _family_from_url(url: str) -> str:
    s = canonical(urlparse(url).path)
    if any(x in s for x in ("partner", "vendor", "fabric", "marca", "portfolio", "line card", "parceir", "alian")):
        return "partners"
    if any(x in s for x in ("career", "job", "emple", "emprego", "talent", "oportun")):
        return "careers"
    if any(x in s for x in ("case", "caso", "customer", "client", "project", "industr", "sector")):
        return "cases"
    if any(x in s for x in ("service", "servic", "solu", "cyber", "cloud", "network")):
        return "services"
    if any(x in s for x in ("news", "press", "notic", "insight")):
        return "news"
    return "official"


def _match_terms(text: str, dictionary: dict[str, list[str]]) -> list[str]:
    blob = " " + canonical(text) + " "
    result = []
    for label, terms in dictionary.items():
        if any(canonical(term) in blob for term in terms):
            result.append(label)
    return result


def _vendor_names(data: dict[str, Any]) -> list[str]:
    names = []
    for row in data.get("manufacturers") or []:
        name = str(row.get("name") or "")
        if name:
            names.append(name)
            if "/" in name:
                names.extend(x.strip() for x in name.split("/") if x.strip())
    return sorted(set(names), key=len, reverse=True)


def _vendors_in_text(text: str, vendor_names: list[str]) -> list[str]:
    blob = canonical(text)
    found = []
    for vendor in vendor_names:
        token = canonical(vendor)
        if len(token) < 3:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob):
            found.append(vendor)
    # collapse aliases such as Akamai + Noname back to the canonical row name where possible later
    return list(dict.fromkeys(found))[:80]


def _page_candidates(section: str, family: str, text: str, vendors: list[str]) -> dict[str, tuple[list[str], str, float]]:
    out: dict[str, tuple[list[str], str, float]] = {}
    if section in {"integrators", "distributors"}:
        if family == "partners":
            found = _vendors_in_text(text, vendors)
            if found:
                out["vendor_relations"] = (found, "fact", 0.86)
        if family in {"services", "official"}:
            caps = _match_terms(text, CAPABILITY_TERMS)
            serv = _match_terms(text, SERVICE_TERMS)
            if caps: out["capabilities"] = (caps, "fact", 0.84)
            if serv: out["services"] = (serv, "fact", 0.84)
        if family == "cases":
            verticals = _match_terms(text, VERTICAL_TERMS)
            if verticals: out["verticals"] = (verticals, "fact", 0.82)
        if family == "careers":
            jobs = _match_terms(text, JOB_PROFILE_TERMS)
            job_vendors = _vendors_in_text(text, vendors)
            if jobs: out["job_profiles"] = (jobs, "signal", 0.58)
            if job_vendors: out["job_vendors"] = (job_vendors, "signal", 0.56)
    elif section == "clients_private":
        if family in {"careers", "technology", "services", "official"}:
            tech = _match_terms(text, CAPABILITY_TERMS)
            if tech: out["technology_signals"] = (tech, "signal", 0.56)
        if family == "careers":
            jobs = _match_terms(text, JOB_PROFILE_TERMS)
            if jobs: out["hiring_signals"] = (jobs, "signal", 0.56)
    elif section == "manufacturers" and family in {"services", "official", "technology"}:
        caps = _match_terms(text, CAPABILITY_TERMS)
        if caps: out["capabilities"] = (caps, "fact", 0.84)
    return out


def run(profile: str = "daily", max_runtime: int = 600, max_tasks: int | None = None) -> dict[str, Any]:
    started = time.monotonic(); deadline = started + max(20, int(max_runtime))
    data = _load("data/current/intelligence.json", {})
    gaps = _load("data/current/research_gaps.json", {})
    learning = _load("data/current/research_learning.json", {"version": VERSION, "families": {}})
    cache = _load("data/current/research_cache.json", {})
    targets = plan(gaps, learning, profile, max_tasks=max_tasks)
    index = _row_index(data)
    vendors = _vendor_names(data)
    stats = {
        "version": VERSION, "profile": profile, "started_at": _now(), "planned_entities": len(targets),
        "fetch_attempts": 0, "fetch_successes": 0, "pages_relevant": 0, "candidate_evidences": 0,
        "accepted_evidences": 0, "fields_enriched": 0, "values_added": 0, "cache_hits": 0,
        "stop_reason": "complete", "families": defaultdict(lambda: defaultdict(int)), "results": [],
    }
    session = requests.Session(); session.headers.update({"User-Agent": UA, "Accept-Language": "es,pt;q=0.9,en;q=0.8"})
    profile_pages = {"daily": 4, "deep": 12, "exhaustive": 24}.get(profile, 4)
    profile_timeout = {"daily": 6, "deep": 8, "exhaustive": 10}.get(profile, 6)

    def fetch(url: str) -> tuple[bool, str, str, list[str], bool, str]:
        key = hashlib.sha1(url.encode("utf-8")).hexdigest(); cached = cache.get(key)
        if cached and cached.get("ok") and time.time() - float(cached.get("ts") or 0) < 86400:
            stats["cache_hits"] += 1
            return True, cached.get("text", ""), cached.get("title", ""), cached.get("links", []), True, cached.get("url", url)
        remain = deadline - time.monotonic()
        if remain <= 2:
            return False, "", "", [], False, url
        try:
            response = session.get(url, timeout=max(2, min(profile_timeout, remain - 1)), allow_redirects=True)
            stats["fetch_attempts"] += 1
            if response.status_code >= 400:
                return False, "", "", [], False, response.url
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
                return False, "", "", [], False, response.url
            parser = TextExtractor(); parser.feed(response.text[:2_500_000])
            links = []
            host = urlparse(response.url).netloc.lower()
            for raw in parser.links:
                target = urldefrag(urljoin(response.url, raw))[0]
                parsed = urlparse(target)
                if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host and PAGE_HINT.search(parsed.path):
                    links.append(target)
            links = list(dict.fromkeys(links))[:80]
            cache[key] = {"ok": True, "url": response.url, "text": parser.text[:1_500_000], "title": parser.title, "links": links, "ts": time.time()}
            return True, parser.text, parser.title, links, False, response.url
        except requests.RequestException:
            stats["fetch_attempts"] += 1
            return False, "", "", [], False, url

    for target in targets:
        if time.monotonic() >= deadline - 4:
            stats["stop_reason"] = "deadline"; break
        row = index.get((target["section"], canonical(target["entity"])))
        if not row:
            continue
        seeds = _official_urls(row)
        if not seeds:
            continue
        base_urls = []
        for seed in seeds:
            p = urlparse(seed); base = f"{p.scheme}://{p.netloc}"
            for family in target.get("families") or ["official"]:
                for route in ROUTES.get(family, ROUTES["official"]):
                    base_urls.append((urljoin(base, route), family))
            base_urls.append((seed, _family_from_url(seed)))
        queue = list(dict.fromkeys(base_urls)); seen = set(); pages = 0
        while queue and pages < profile_pages and time.monotonic() < deadline - 3:
            url, hinted_family = queue.pop(0)
            if url in seen: continue
            seen.add(url)
            ok, text, title, links, cached, final_url = fetch(url)
            family = _family_from_url(final_url) if ok else hinted_family
            fstats = stats["families"][f"{target['section']}:{family}"]
            fstats["attempts"] += 1
            if not ok:
                continue
            stats["fetch_successes"] += 1; fstats["fetch_successes"] += 1; pages += 1
            candidates = _page_candidates(target["section"], family, text, vendors)
            relevant = bool(candidates) or PAGE_HINT.search(final_url) is not None
            if relevant:
                stats["pages_relevant"] += 1; fstats["pages_relevant"] += 1
            accepted_here = 0
            for field_id, (vals, claim_type, confidence) in candidates.items():
                if field_id not in target.get("fields", []) and profile == "daily":
                    continue
                if not vals:
                    continue
                stats["candidate_evidences"] += 1; fstats["candidate_evidence"] += 1
                before_values = set(canonical(x) for x in (row.get("fields", {}).get(field_id, {}).get("value") or []) if isinstance(row.get("fields", {}).get(field_id, {}).get("value"), list))
                evidence = [{
                    "source": target["entity"], "title": title or f"Página oficial · {family}", "url": final_url,
                    "date": datetime.now(timezone.utc).date().isoformat(), "description": f"Página oficial de {target['entity']} utilizada para extraer {field_id} con reglas conservadoras.",
                    "scope": str(((row.get("fields") or {}).get("scope") or {}).get("value") or "GLOBAL"),
                    "source_grade": "A", "source_type": "official-domain", "official": True, "classification": "public",
                    "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "freshness_status": "current",
                    "method": f"official-web:{family}",
                }]
                row.setdefault("fields", {})[field_id] = merge_field(row.get("fields", {}).get(field_id), {
                    "value": vals, "evidence": evidence, "confidence": confidence, "claim_type": claim_type,
                    "assertion_status": "SEÑAL" if claim_type == "signal" else "CONFIRMADO",
                    "qualifier": "Extracción automática conservadora desde dominio oficial; las señales de empleo no prueban por sí solas partnership ni despliegue.",
                })
                after = row["fields"][field_id].get("value")
                after_values = set(canonical(x) for x in after) if isinstance(after, list) else {canonical(after)}
                added = len(after_values - before_values)
                stats["values_added"] += max(0, added); stats["fields_enriched"] += int(added > 0)
                stats["accepted_evidences"] += 1; fstats["accepted_evidence"] += 1; accepted_here += 1
            stats["results"].append({"section": target["section"], "entity": target["entity"], "url": final_url, "family": family, "cached": cached, "relevant": relevant, "accepted": accepted_here})
            if profile != "daily" and relevant:
                for link in links:
                    fam = _family_from_url(link)
                    if fam in set(target.get("families") or []) | {"official"} and link not in seen and (link, fam) not in queue:
                        queue.append((link, fam))
        if stats["results"] and len(stats["results"]) % 25 == 0:
            # Durable checkpoint: a hard timeout may kill the research subprocess, but accepted evidence survives.
            _save("data/current/intelligence.json", data)
            _save("data/current/research_cache.json", cache)
            _save("data/current/research_ledger.json", {k: v for k, v in stats.items() if k not in {"results", "families"}} | {"results": stats["results"][-250:]})

    # Update yield learning with evidence yield, not HTTP success.
    families_out = {}
    for key, row_stats in stats["families"].items():
        current = (learning.setdefault("families", {}).setdefault(key, {}))
        for metric in ("attempts", "fetch_successes", "pages_relevant", "candidate_evidence", "accepted_evidence"):
            current[metric] = int(current.get(metric) or 0) + int(row_stats.get(metric) or 0)
        current["fetch_success_rate"] = round(current["fetch_successes"] / max(1, current["attempts"]), 4)
        current["evidence_yield"] = round(current["accepted_evidence"] / max(1, current["pages_relevant"]), 4)
        families_out[key] = dict(row_stats)
    learning["version"] = VERSION; learning["updated_at"] = _now(); learning["policy"] = "Prioritize evidence yield and gap closure; HTTP 200 is transport success only."
    stats["families"] = families_out; stats["elapsed_s"] = round(time.monotonic() - started, 2)
    _save("data/current/intelligence.json", data)
    _save("data/current/research_learning.json", learning)
    _save("data/current/research_ledger.json", {k: v for k, v in stats.items() if k != "results"} | {"results": stats["results"][-1000:]})
    if len(cache) > 1800:
        cache = dict(sorted(cache.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True)[:1200])
    _save("data/current/research_cache.json", cache)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["daily", "deep", "exhaustive"], default="daily")
    parser.add_argument("--max-runtime", type=int, default=600)
    parser.add_argument("--max-tasks", type=int, default=None)
    args = parser.parse_args()
    result = run(args.profile, max_runtime=args.max_runtime, max_tasks=args.max_tasks)
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False))
