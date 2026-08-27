from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

UA = "Westcon-Iberia-Decision-Intelligence/3.2 public-research"


def _request(url: str, *, timeout: int = 8, data: bytes | None = None, headers: Mapping[str, str] | None = None) -> bytes:
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(dict(headers or {}))
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url: str, *, timeout: int = 8, payload: Mapping[str, Any] | None = None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return json.loads(_request(url, timeout=timeout, data=data, headers=headers).decode("utf-8", errors="replace"))


def _multi(v: Any) -> str:
    if isinstance(v, str): return v
    if isinstance(v, list): return " / ".join(_multi(x) for x in v if x)
    if isinstance(v, dict):
        for k in ("spa", "por", "eng"):
            if k in v: return _multi(v[k])
        return _multi(next(iter(v.values()), ""))
    return str(v or "")


def _entity_aliases(entities: Iterable[Mapping[str, Any]]) -> List[Tuple[str, str, str, str]]:
    out=[]
    for e in entities:
        name=str(e.get("name") or "").strip()
        if not name: continue
        base=re.sub(r"\s+(spain|portugal|iberia|españa)$", "", name, flags=re.I).strip()
        out.append((name,base.casefold(),str(e.get("entity_type") or "entity"),str(e.get("country") or "GLOBAL")))
    return out



AMBIGUOUS_ENTITY_WORDS={"timestamp","insight","orange","everis"}
TECH_CPV_PREFIXES=("302","324","325","480","481","482","483","484","485","486","487","488","489","50312","5033","5161","642","720","721","722","723","724","725","726","727","728","729")
TECH_PROCUREMENT_RE=re.compile(
    r"\b(software|inform[aá]tic[oa]s?|tecnolog[ií]a(?:s)? de la informaci[oó]n|technology|information technology|tic|ict|"
    r"telecom(?:unicaciones|unica[cç][oõ]es)?|red(?:es)?(?: de datos)?|network(?:ing|s)?|ciberseguridad|cybersecurity|"
    r"seguridad (?:it|de red|inform[aá]tica)|firewall|siem|soc|xdr|edr|sase|zero trust|cloud|nube|nuvem|"
    r"data ?center|centro de datos|servidor(?:es)?|server(?:s)?|ordenador(?:es)?|computer(?:s)?|tablet(?:as)?|"
    r"infraestructura (?:it|tic|digital|de red)|monitorizaci[oó]n|monitoriza[cç][aã]o|inteligencia artificial|artificial intelligence|\bia\b|\bai\b)\b",
    re.I,
)

def _norm_text(value: Any) -> str:
    return re.sub(r"\s+"," ",str(value or "")).strip()

def _alias_in_text(alias: str, text: str, *, strict_short: bool=True) -> bool:
    alias=_norm_text(alias); text=_norm_text(text)
    if not alias or not text:return False
    # Exact token/phrase boundaries prevent Atos matching "contratos" and MCR matching random codes.
    if strict_short and (alias.casefold() in AMBIGUOUS_ENTITY_WORDS or (len(alias)<=4 and alias.isupper())):
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",text))
    return bool(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)",text,re.I))

def _matched_entities(text: str, aliases: Iterable[Tuple[str,str,str,str]], *, strict_short: bool=True) -> List[Tuple[str,str,str,str]]:
    out=[]
    for row in aliases:
        name=row[0]; base=re.sub(r"\s+(spain|portugal|iberia|españa)$","",name,flags=re.I).strip()
        if _alias_in_text(base,text,strict_short=strict_short) or _alias_in_text(name,text,strict_short=strict_short):
            out.append(row)
    return out

def _cpv_codes(value: Any) -> List[str]:
    vals=[]
    blob=_multi(value)
    for m in re.findall(r"(?<!\d)(\d{8})(?:-\d)?(?!\d)",blob):
        if m not in vals: vals.append(m)
    return vals

def procurement_is_technology(record: Mapping[str,Any]) -> bool:
    cpvs=[]
    for k in ("cpv","classification_cpv","raw_text","summary"):
        cpvs.extend(_cpv_codes(record.get(k)))
    if any(any(code.startswith(pref) for pref in TECH_CPV_PREFIXES) for code in cpvs): return True
    blob=" ".join(str(record.get(k) or "") for k in ("title","summary","raw_text"))
    return bool(TECH_PROCUREMENT_RE.search(blob))

STRATEGIC_PROCUREMENT_RE=re.compile(
    r"\b(ciberseguridad|cybersecurity|firewall|siem|soc|xdr|edr|sase|sse|zero trust|pam|iam|identity|identidad|"
    r"network(?:ing|s)?|red(?:es)? de datos|switch(?:es)?|router(?:s)?|wifi|wi-fi|sd-wan|ethernet|5g|"
    r"cloud|nube|nuvem|data ?center|centro de datos|servidor(?:es)?|storage|almacenamiento|"
    r"monitorizaci[oó]n|observabilidad|observability|telemetr[ií]a|automation|automatizaci[oó]n|orquestaci[oó]n|"
    r"inteligencia artificial|artificial intelligence|agentic|genai|\bia\b|\bai\b)\b", re.I
)

def procurement_fit_score(record: Mapping[str,Any]) -> float:
    """Fit of a public tender to Westcon's strategic technology domains.

    Broad IT/software procurement is retained as evidence but does not become an automatic
    commercial opportunity. Networking, cyber, cloud, data-center, AI, observability,
    automation and identity score materially higher.
    """
    blob=" ".join(str(record.get(k) or "") for k in ("title","summary","raw_text"))
    cpvs=[]
    for k in ("cpv","classification_cpv","raw_text","summary"):
        cpvs.extend(_cpv_codes(record.get(k)))
    score=.20 if procurement_is_technology(record) else 0.0
    if STRATEGIC_PROCUREMENT_RE.search(blob): score=max(score,.78)
    # Networking/telecom and data infrastructure CPVs are especially aligned.
    if any(code.startswith(("324","325","50312","5033","642")) for code in cpvs): score=max(score,.82)
    # Generic software/IT services and end-user computing are useful context but weaker fit.
    if any(code.startswith(("48","72")) for code in cpvs) and score<.78: score=max(score,.42)
    if any(code.startswith("302") for code in cpvs) and score<.78: score=max(score,.36)
    return round(min(1.0,score),3)

def _local(tag: str) -> str:
    return str(tag or "").split("}")[-1].split(":")[-1]

def _party_name_under(node: ET.Element, ancestor_names: set[str]) -> str:
    for anc in node.iter():
        if _local(anc.tag) not in ancestor_names: continue
        # Prefer PartyName/Name but accept CorporateRegistrationScheme/Name variants conservatively.
        for sub in anc.iter():
            if _local(sub.tag)=="Name" and (sub.text or "").strip():
                return (sub.text or "").strip()[:240]
    return ""

def _procurement_meta(node: ET.Element) -> Dict[str,Any]:
    buyer=_party_name_under(node,{"ContractingParty","ContractingAuthority","Buyer"})
    winner=_party_name_under(node,{"WinningParty","Winner","TendererParty"})
    cpvs=[]; statuses=[]
    for sub in node.iter():
        local=_local(sub.tag); txt=(sub.text or "").strip()
        if not txt: continue
        if local in {"ItemClassificationCode","ClassificationCode","MainCommodityClassification"}:
            cpvs.extend(_cpv_codes(txt))
        if local in {"ContractFolderStatusCode","TenderResultCode","AwardStatusCode","StatusCode"}:
            statuses.append(txt)
    return {"buyer_name":buyer,"winner_name":winner,"cpv":" / ".join(dict.fromkeys(cpvs)),"procurement_status":" / ".join(statuses[:6])}

def _procurement_phase(record: Mapping[str,Any]) -> str:
    nt=_multi(record.get("notice_type")).casefold().strip()
    if nt.startswith("can-") or nt in {"compl","result"}: return "award"
    if str(record.get("winner_name") or "").strip(): return "award"
    blob=(str(record.get("procurement_status") or "")+" "+str(record.get("summary") or "")).casefold()
    if re.search(r"\b(adjudicad|adjudica[cç][aã]o|formalizad|awarded|winner|ganador)\b",blob,re.I): return "award"
    return "notice"

def _http_error_detail(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body=exc.read(1400).decode("utf-8",errors="replace").replace("\n"," ")
        except Exception:
            body=""
        return f"HTTP {exc.code}: {body[:900]}".strip()
    return f"{type(exc).__name__}: {exc}"


def _ted_country_queries(profile: str) -> List[Tuple[str,str]]:
    days={"daily":120,"weekly":365,"monthly":1095}.get(profile,120)
    cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).strftime("%Y%m%d")
    return [
        ("ESP", f"buyer-country = ESP AND publication-date >= {cutoff} SORT BY publication-date DESC"),
        ("PRT", f"buyer-country = PRT AND publication-date >= {cutoff} SORT BY publication-date DESC"),
    ]


def ted_search(conn: Mapping[str, Any], entities: Iterable[Mapping[str, Any]], *, profile: str, timeout: int, max_entities: int = 18) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Bulk TED pull for Spain/Portugal with high-precision entity attribution.

    Procurement notices are filtered to technology-relevant CPVs/titles. Seeded entities are
    attributed only when they appear as a winner (not merely somewhere in the title/body).
    Unmatched but relevant notices are retained as market-level demand signals.
    """
    start=time.monotonic(); out=[]; failures=0; successful=0; errors=[]; raw_notices=0; tech_notices=0
    aliases=[x for x in _entity_aliases(entities) if x[2] in {"integrator","distributor"}]
    fields=["publication-number","publication-date","notice-type","notice-title","buyer-name","buyer-country","winner-name","classification-cpv"]
    limit=180 if profile=="daily" else 250
    for cc,q in _ted_country_queries(profile):
        payload={"query":q,"fields":fields,"limit":limit,"paginationMode":"PAGE_NUMBER","page":1}
        try:
            data=_json(str(conn["url"]),timeout=max(timeout,8),payload=payload); successful+=1
        except Exception as exc:
            failures+=1; errors.append(f"{cc}: {_http_error_detail(exc)}"); continue
        for n in data.get("notices",[]) or []:
            raw_notices+=1
            pub=_multi(n.get("publication-number")); title=_multi(n.get("notice-title")) or f"TED notice {pub}"
            buyer=_multi(n.get("buyer-name")); winner=_multi(n.get("winner-name")); cpv=_multi(n.get("classification-cpv")); notice_type=_multi(n.get("notice-type"))
            base={"title":title,"summary":"; ".join(x for x in [f"Buyer: {buyer}" if buyer else "",f"Winner: {winner}" if winner else "",f"CPV: {cpv}" if cpv else "",f"Notice type: {notice_type}" if notice_type else ""] if x),"cpv":cpv}
            if not procurement_is_technology(base): continue
            tech_notices+=1
            phase=_procurement_phase({**base,"winner_name":winner,"notice_type":notice_type})
            matches=_matched_entities(winner,aliases,strict_short=True) if winner else []
            country_code="ES" if cc=="ESP" else "PT"
            if matches:
                targets=matches[:4]
            else:
                targets=[("Iberia Public Procurement Market","iberia public procurement market","market",country_code)]
            for name,_,etype,_seed_country in targets:
                out.append({
                    "entity_name":name,"entity_type":etype,"country":country_code,"title":title,"summary":base["summary"],
                    "published_at":_multi(n.get("publication-date")),"url":f"https://ted.europa.eu/en/notice/-/detail/{pub}" if pub else "https://ted.europa.eu",
                    "source":"TED EU Procurement","source_id":"ted","source_category":"official","source_authority":float(conn.get("authority",.98)),
                    "dimension":"procurement_award" if phase=="award" else "procurement_notice","direct_evidence":True,
                    "evidence_kind":"public_procurement","procurement_phase":phase,"technology_procurement":True,"procurement_fit_score":procurement_fit_score(base),
                    "buyer_name":buyer,"winner_name":winner,"cpv":cpv,"notice_type":notice_type,"procurement_country":cc,"external_id":pub
                })
    return out,{"attempted":2,"successful":successful,"failed":failures,"rows":len(out),"raw_notices":raw_notices,"technology_notices":tech_notices,"errors":errors[:6],"latency_ms":round((time.monotonic()-start)*1000,1)}

def _parse_feed(xml: bytes, source: Mapping[str, Any]) -> List[Dict[str, Any]]:
    root=ET.fromstring(xml); out=[]
    for item in root.findall(".//item")[:80]:
        raw=" ".join(x.strip() for x in item.itertext() if x and x.strip()); meta=_procurement_meta(item)
        out.append({
            "title":item.findtext("title") or "","summary":item.findtext("description") or raw[:5000],"raw_text":raw[:12000],"url":item.findtext("link") or "",
            "published_at":item.findtext("pubDate") or item.findtext("date") or "","source":source.get("name"),"source_id":source.get("id"),
            "source_category":source.get("category"),"source_authority":source.get("authority",.6),"direct_evidence":True,**meta
        })
    if out:return out
    for entry in root.findall(".//{*}entry")[:80]:
        link=""
        for ln in entry.findall("{*}link"):
            if ln.attrib.get("href"):link=ln.attrib["href"];break
        raw=" ".join(x.strip() for x in entry.itertext() if x and x.strip()); meta=_procurement_meta(entry)
        out.append({
            "title":entry.findtext("{*}title") or "","summary":entry.findtext("{*}summary") or entry.findtext("{*}content") or raw[:5000],"raw_text":raw[:12000],
            "url":link,"published_at":entry.findtext("{*}published") or entry.findtext("{*}updated") or "","source":source.get("name"),
            "source_id":source.get("id"),"source_category":source.get("category"),"source_authority":source.get("authority",.6),"direct_evidence":True,**meta
        })
    return out

def atom_feed(conn: Mapping[str, Any], registry: Iterable[Mapping[str, Any]], entities: Iterable[Mapping[str, Any]], *, timeout: int, state_dir: Path | None = None, profile: str = "daily") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    start=time.monotonic(); aliases=[x for x in _entity_aliases(entities) if x[2] in {"integrator","distributor"}]; errors=[]
    src=next((s for s in registry if s.get("id")==conn.get("source_id")),{"id":conn.get("source_id"),"name":conn.get("source_id"),"category":"official","authority":conn.get("authority",.95)})
    urls=[]
    for u in [conn.get("url")]+list(conn.get("fallback_urls") or []):
        if u and u not in urls:urls.append(str(u))
    cache_file = (state_dir / f"connector_cache_{str(conn.get('source_id') or conn.get('id') or 'atom')}.json") if state_dir else None
    attempts=0
    for u in urls:
        # Two bounded attempts protect the daily run from transient PLACSP/Atom resets.
        for retry in range(2):
            attempts += 1
            try:
                feed=_parse_feed(_request(u,timeout=max(timeout,10)),src);out=[];tech_rows=0;matched_rows=0
                for r in feed:
                    if not procurement_is_technology(r):continue
                    tech_rows+=1;phase=_procurement_phase(r);winner=str(r.get("winner_name") or "").strip();matches=_matched_entities(winner,aliases,strict_short=True) if winner else []
                    targets=matches[:4] if matches else [("Iberia Public Procurement Market","iberia public procurement market","market",str(conn.get("country") or "ES"))]
                    matched_rows+=int(bool(matches))
                    for name,_,etype,country in targets:
                        rr=dict(r);rr.update({
                            "entity_name":name,"entity_type":etype,"country":country,"dimension":"procurement_award" if phase=="award" else "procurement_notice","feed_url":u,
                            "evidence_kind":"public_procurement","procurement_phase":phase,"technology_procurement":True,"procurement_fit_score":procurement_fit_score(r),
                        });out.append(rr)
                if cache_file:
                    try:
                        cache_file.parent.mkdir(parents=True,exist_ok=True)
                        cache_file.write_text(json.dumps({"saved_at":datetime.now(timezone.utc).isoformat(),"url":u,"rows":out},ensure_ascii=False,indent=2),encoding="utf-8")
                    except Exception: pass
                return out,{"attempted":attempts,"successful":1,"failed":0,"rows":len(out),"raw_feed_rows":len(feed),"technology_rows":tech_rows,"entity_matched_rows":matched_rows,"url_used":u,"cached":0,"errors":errors,"latency_ms":round((time.monotonic()-start)*1000,1)}
            except Exception as exc:
                errors.append(f"{u}: {_http_error_detail(exc)}")
                if retry == 0: time.sleep(.35)
    # A temporary source outage must not erase yesterday's valid official evidence.
    if cache_file and cache_file.exists():
        try:
            cached=json.loads(cache_file.read_text(encoding="utf-8")); saved=datetime.fromisoformat(str(cached.get("saved_at") or "").replace("Z","+00:00"))
            age=(datetime.now(timezone.utc)-saved).total_seconds()/86400
            max_age={"daily":3,"weekly":10,"monthly":35}.get(profile,3)
            rows=list(cached.get("rows") or [])
            if rows and age <= max_age:
                for row in rows: row["cache_fallback"]=True
                return rows,{"attempted":attempts,"successful":0,"failed":1,"rows":len(rows),"cached":1,"cache_age_days":round(age,2),"url_used":cached.get("url"),"errors":errors[:4],"latency_ms":round((time.monotonic()-start)*1000,1)}
        except Exception: pass
    return [],{"attempted":attempts,"successful":0,"failed":1,"rows":0,"cached":0,"latency_ms":round((time.monotonic()-start)*1000,1),"errors":errors[:4]}

def cisa_kev(conn: Mapping[str, Any], entities: Iterable[Mapping[str, Any]], *, timeout: int, profile: str="daily") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    start=time.monotonic(); out=[]; aliases=[x for x in _entity_aliases(entities) if x[2]=="vendor"]
    try:
        data=_json(str(conn["url"]),timeout=timeout)
        max_age={"daily":120,"weekly":365,"monthly":1095}.get(profile,365)
        for v in data.get("vulnerabilities",[]) or []:
            try:
                added=datetime.fromisoformat(str(v.get("dateAdded") or ""))
                if (datetime.now()-added).days>max_age: continue
            except Exception: pass
            vendor=str(v.get("vendorProject") or ""); product=str(v.get("product") or ""); cve=str(v.get("cveID") or ""); nv=vendor.casefold(); matched=None
            for name,base,_,country in aliases:
                b=base.replace(" networks","").replace(" software","")
                if b and (b in nv or nv in b): matched=(name,country); break
            if not matched: continue
            out.append({
                "entity_name":matched[0],"entity_type":"vendor","country":matched[1],"title":f"{cve}: {vendor} {product} · explotación conocida (CISA KEV)",
                "summary":str(v.get("shortDescription") or "")+" | Required action: "+str(v.get("requiredAction") or ""),"published_at":v.get("dateAdded"),
                "url":"https://www.cisa.gov/known-exploited-vulnerabilities-catalog","source":"CISA KEV","source_id":"cisa","source_category":"regulatory",
                "source_authority":float(conn.get("authority",.99)),"dimension":"known_exploited_vulnerability","direct_evidence":True,"cve":cve,"product":product,"vendor_project":vendor,"due_date":v.get("dueDate")
            })
        return out,{"attempted":1,"failed":0,"rows":len(out),"latency_ms":round((time.monotonic()-start)*1000,1)}
    except Exception as exc:
        return [],{"attempted":1,"failed":1,"rows":0,"latency_ms":round((time.monotonic()-start)*1000,1),"error":type(exc).__name__}


def epss_scores(conn: Mapping[str, Any], cves: Iterable[str], *, timeout: int) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Any]]:
    wanted={str(x).upper() for x in cves if x}; start=time.monotonic()
    if not wanted: return {},{"attempted":0,"failed":0,"rows":0,"latency_ms":0}
    try:
        text=gzip.decompress(_request(str(conn["url"]),timeout=timeout)).decode("utf-8",errors="replace")
        lines=[x for x in text.splitlines() if not x.startswith("#")]; reader=csv.DictReader(io.StringIO("\n".join(lines))); out={}
        for r in reader:
            cve=str(r.get("cve") or "").upper()
            if cve in wanted:
                try: out[cve]={"epss":float(r.get("epss") or 0),"percentile":float(r.get("percentile") or 0)}
                except Exception: pass
        return out,{"attempted":1,"failed":0,"rows":len(out),"latency_ms":round((time.monotonic()-start)*1000,1)}
    except Exception as exc:
        return {},{"attempted":1,"failed":1,"rows":0,"latency_ms":round((time.monotonic()-start)*1000,1),"error":type(exc).__name__}


def nvd_search(conn: Mapping[str, Any], entities: Iterable[Mapping[str, Any]], *, timeout: int, max_entities: int=5) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    start=time.monotonic(); out=[]; failures=0
    chosen=[x for x in entities if x.get("entity_type")=="vendor"][:max_entities]
    def one(e):
        name=str(e.get("name") or ""); url=str(conn["url"])+"?"+urllib.parse.urlencode({"keywordSearch":name,"resultsPerPage":8});data=_json(url,timeout=timeout);rows=[]
        for item in data.get("vulnerabilities",[]) or []:
            c=item.get("cve") or {}; cve=str(c.get("id") or ""); desc=""
            for d in c.get("descriptions",[]) or []:
                if d.get("lang")=="en": desc=d.get("value") or ""; break
            rows.append({"entity_name":name,"entity_type":"vendor","country":e.get("country","GLOBAL"),"title":f"{cve} · NVD vulnerability affecting {name}","summary":desc,"published_at":c.get("published"),"url":f"https://nvd.nist.gov/vuln/detail/{cve}" if cve else "https://nvd.nist.gov","source":"NVD","source_id":"nvd","source_category":"regulatory","source_authority":float(conn.get("authority",.97)),"dimension":"security_vulnerability","direct_evidence":True,"cve":cve})
        return rows
    with ThreadPoolExecutor(max_workers=min(3,max(1,len(chosen)))) as ex:
        futs=[ex.submit(one,e) for e in chosen]
        for f in as_completed(futs):
            try:out.extend(f.result())
            except Exception:failures+=1
    return out,{"attempted":len(chosen),"failed":failures,"rows":len(out),"latency_ms":round((time.monotonic()-start)*1000,1)}


def sec_filings(conn: Mapping[str, Any], entities: Iterable[Mapping[str, Any]], *, timeout: int, max_entities: int=8) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    start=time.monotonic(); out=[]; failures=0
    try:
        tickers=_json(str(conn["tickers_url"]),timeout=timeout)
    except Exception as exc:
        return [],{"attempted":1,"failed":1,"rows":0,"latency_ms":round((time.monotonic()-start)*1000,1),"error":type(exc).__name__}
    lookup=[]
    for v in tickers.values() if isinstance(tickers,dict) else []:
        lookup.append((str(v.get("title") or "").casefold(),str(v.get("ticker") or "").casefold(),int(v.get("cik_str") or 0)))
    chosen=[]
    for e in [x for x in entities if x.get("entity_type")=="vendor"]:
        name=str(e.get("name") or ""); b=name.casefold().replace(" networks","").replace(" software","")
        hit=next((x for x in lookup if b and (b in x[0] or x[0] in b)),None)
        if hit: chosen.append((e,hit[2]))
        if len(chosen)>=max_entities: break
    def one(pair):
        e,cik=pair; url=str(conn["submissions_base"]).format(cik=str(cik).zfill(10));data=_json(url,timeout=timeout);rec=(data.get("filings") or {}).get("recent") or {};rows=[]
        forms=rec.get("form") or [];dates=rec.get("filingDate") or [];access=rec.get("accessionNumber") or [];docs=rec.get("primaryDocument") or []
        for i,form in enumerate(forms[:120]):
            if form not in {"8-K","10-Q","10-K","20-F","6-K"}: continue
            try: date=dates[i]; acc=access[i].replace("-",""); doc=docs[i]
            except Exception: continue
            try:
                dt=datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc)-dt).days>400: continue
            except Exception: pass
            ciknum=str(cik); filing_url=f"https://www.sec.gov/Archives/edgar/data/{ciknum}/{acc}/{doc}"
            rows.append({"entity_name":e.get("name"),"entity_type":"vendor","country":e.get("country","GLOBAL"),"title":f"SEC filing {form} · {e.get('name')}","summary":f"Official SEC filing form {form}","published_at":date,"url":filing_url,"source":"SEC EDGAR","source_id":"sec_edgar","source_category":"official","source_authority":float(conn.get("authority",.99)),"dimension":"financial_performance","direct_evidence":True})
        return rows[:8]
    with ThreadPoolExecutor(max_workers=min(3,max(1,len(chosen)))) as ex:
        futs=[ex.submit(one,x) for x in chosen]
        for f in as_completed(futs):
            try: out.extend(f.result())
            except Exception: failures+=1
    return out,{"attempted":1+len(chosen),"failed":failures,"rows":len(out),"latency_ms":round((time.monotonic()-start)*1000,1)}


def _source_priority(src: Mapping[str,Any], learning: Mapping[str,Any]) -> float:
    sid=str(src.get("id")); st=learning.get(sid,{}) if isinstance(learning,Mapping) else {}; attempts=int(st.get("attempts",0)); successes=int(st.get("successes",0)); rows=int(st.get("rows",0))
    category=str(src.get("category")); cat={"official":.22,"regulatory":.22,"vendor":.20,"distributor":.19,"integrator":.19,"analyst":.17,"channel_media":.13,"web_footprint":.09}.get(category,.10)
    auth=float(src.get("authority",.55)); success_rate=(successes+1)/(attempts+2); yield_rate=min(1.0,rows/max(1,attempts*5)); exploration=.18/math.sqrt(attempts+1)
    quality=float(st.get("avg_materiality",.50) or .50); high_rate=(float(st.get("high_materiality",0))+1)/(float(st.get("event_count",0))+3)
    stale=.10
    try:
        last=datetime.fromisoformat(str(st.get("last_attempt") or "").replace("Z","+00:00")); stale=min(.18,max(0,(datetime.now(timezone.utc)-last).days/30*.06))
    except Exception: pass
    return .30*auth+cat+.14*success_rate+.08*yield_rate+.11*quality+.06*high_rate+exploration+stale


def _discover_feed_links(base: str, timeout: int) -> List[str]:
    try:
        html=_request(base,timeout=max(4,min(timeout,8))).decode("utf-8",errors="replace")[:500000]
    except Exception:
        return []
    links=[]
    for tag in re.findall(r"<link\b[^>]*>",html,re.I):
        if not re.search(r"type\s*=\s*['\"]application/(?:rss\+xml|atom\+xml)['\"]",tag,re.I): continue
        m=re.search(r"href\s*=\s*['\"]([^'\"]+)['\"]",tag,re.I)
        if m:
            u=urllib.parse.urljoin(base,m.group(1).strip())
            if u not in links: links.append(u)
    return links[:4]


def _feed_date(value: Any) -> datetime | None:
    if not value: return None
    text=str(value).strip()
    try:
        d=datetime.fromisoformat(text.replace("Z","+00:00")); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: pass
    try:
        from email.utils import parsedate_to_datetime
        d=parsedate_to_datetime(text); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: return None

def _feed_row_fresh(row: Mapping[str,Any], profile: str) -> bool:
    d=_feed_date(row.get("published_at") or row.get("date"))
    if not d: return True
    max_age={"daily":180,"weekly":550,"monthly":1460}.get(profile,365)
    return (datetime.now(timezone.utc)-d.astimezone(timezone.utc)).days <= max_age

def generic_feeds(registry: Iterable[Mapping[str,Any]], entities: Iterable[Mapping[str,Any]], cfg: Mapping[str,Any], *, timeout:int, cap:int, state_dir:Path, profile:str="daily") -> Tuple[List[Dict[str,Any]],Dict[str,Any]]:
    start=time.monotonic(); cache_path=state_dir/"feed_cache.json"; learning_path=state_dir/"source_learning.json"
    try: cache=json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except Exception: cache={}
    try: learning=json.loads(learning_path.read_text(encoding="utf-8")) if learning_path.exists() else {}
    except Exception: learning={}
    aliases=_entity_aliases(entities); paths=list((cfg.get("generic_feed") or {}).get("paths") or ["/feed","/rss.xml"]);max_new=int((cfg.get("generic_feed") or {}).get("max_paths_per_new_source",2))
    sources=[s for s in registry if s.get("category")!="discovery" and s.get("enabled",True) is not False and s.get("domains")]
    sources=sorted(sources,key=lambda s:(_source_priority(s,learning),hashlib.sha1(str(s.get("id")).encode()).hexdigest()),reverse=True)[:cap]

    def probe(src):
        sid=str(src.get("id")); domains=src.get("domains") or []; urls=[]; last_error=""
        if cache.get(sid,{}).get("url"): urls.append(cache[sid]["url"])
        base="https://"+str(domains[0]).strip().rstrip("/")
        if not urls:
            urls.extend(_discover_feed_links(base,timeout))
            urls.extend(base+p for p in paths[:max_new])
        # unique while preserving order
        urls=list(dict.fromkeys(urls))[:max(3,max_new+2)]
        attempts=0; rows=[]; working=""
        for u in urls:
            attempts+=1
            try:
                rows=_parse_feed(_request(u,timeout=timeout),src)
                if rows: working=u;break
            except Exception as exc:
                last_error=_http_error_detail(exc)
        return src,attempts,rows,working,last_error,bool(cache.get(sid,{}).get("url"))

    out=[];per={}
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(sources)))) as ex:
        futs=[ex.submit(probe,s) for s in sources]
        for f in as_completed(futs):
            src,attempts,rows,working,last_error,had_cached_feed=f.result();sid=str(src.get("id")); seeds=[e for e in src.get("seed_entities") or [] if isinstance(e,Mapping)];accepted=0
            if working: cache[sid]={"url":working,"last_ok":datetime.now(timezone.utc).isoformat()}
            row_cap={"daily":25,"weekly":60,"monthly":120}.get(profile,40)
            rows=[r for r in rows if _feed_row_fresh(r,profile)][:row_cap]
            stale_filtered=max(0,int(per.get(sid,{}).get("feed_rows",0))-len(rows)) if sid in per else 0
            for r in rows:
                blob=(str(r.get("title"))+" "+str(r.get("summary"))+" "+str(r.get("raw_text")))
                # A first-party vendor/distributor/integrator feed belongs to its seeded entity.
                # Media/analyst feeds require exact phrase/token matching; never substring matching.
                if seeds and str(src.get("category") or "") in {"vendor","distributor","integrator"}:
                    matches=[(str(seeds[0].get("name")),str(seeds[0].get("name")).casefold(),str(seeds[0].get("entity_type")),str(seeds[0].get("country") or "GLOBAL"))]
                else:
                    matches=_matched_entities(blob,aliases,strict_short=True)
                if matches:
                    for name,_,etype,country in matches[:2]:
                        rr=dict(r);rr.update({"entity_name":name,"entity_type":etype,"country":country});out.append(rr);accepted+=1
                elif src.get("category") in {"analyst","regulatory","official"} and re.search(r"\b(ai|cloud|cyber|security|network|sase|zero trust|data center|datacenter|automation|observability|channel|partner|regulation)\b",blob,re.I):
                    rr=dict(r);rr.update({"entity_name":"Iberia Technology Market","entity_type":"market","country":"IBERIA"});out.append(rr);accepted+=1
            st=learning.setdefault(sid,{"attempts":0,"successes":0,"rows":0});st["attempts"]+=1;st["successes"]+=int(bool(rows));st["rows"]+=accepted;st["last_attempt"]=datetime.now(timezone.utc).isoformat();st["last_success"]=datetime.now(timezone.utc).isoformat() if rows else st.get("last_success")
            status="ok" if rows else ("error" if had_cached_feed and last_error else "no_feed")
            per[sid]={"attempts":attempts,"feed_rows":len(rows),"accepted_rows":accepted,"working_feed":working,"error":last_error,"row_cap":row_cap,"status":status}
    cache_path.parent.mkdir(parents=True,exist_ok=True);cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding="utf-8");learning_path.write_text(json.dumps(learning,ensure_ascii=False,indent=2),encoding="utf-8")
    successful=sum(1 for x in per.values() if x.get("status")=="ok"); errors=sum(1 for x in per.values() if x.get("status")=="error"); no_feed=sum(1 for x in per.values() if x.get("status")=="no_feed")
    return out,{"attempted_sources":len(sources),"successful_sources":successful,"failed_sources":errors,"no_feed_sources":no_feed,"failed":errors,"rows":len(out),"per_source":per,"latency_ms":round((time.monotonic()-start)*1000,1)}

def run_direct_sources(registry: List[Mapping[str,Any]], entities: List[Mapping[str,Any]], config: Mapping[str,Any], *, profile:str, timeout:int, source_cap:int, state_dir:Path) -> Tuple[List[Dict[str,Any]],Dict[str,Any]]:
    rows=[];stats={};connectors=config.get("connectors") or []
    for conn in connectors:
        cid=str(conn.get("id")); profiles=conn.get("profiles") or []
        if profile not in profiles: continue
        if not conn.get("enabled",True):
            stats[cid]={"attempted":0,"failed":0,"rows":0,"status":"disabled","reason":conn.get("reason")};continue
        kind=conn.get("kind")
        try:
            if kind=="ted": r,s=ted_search(conn,entities,profile=profile,timeout=timeout,max_entities=10 if profile=="daily" else 25)
            elif kind=="atom_feed": r,s=atom_feed(conn,registry,entities,timeout=timeout,state_dir=state_dir,profile=profile)
            elif kind=="cisa_kev": r,s=cisa_kev(conn,entities,timeout=timeout,profile=profile)
            elif kind=="nvd": r,s=nvd_search(conn,entities,timeout=timeout,max_entities=5 if profile=="weekly" else 12)
            elif kind=="sec": r,s=sec_filings(conn,entities,timeout=timeout,max_entities=6 if profile=="weekly" else 12)
            else: continue
            rows.extend(r);stats[cid]=s
        except Exception as exc: stats[cid]={"attempted":1,"failed":1,"rows":0,"error":type(exc).__name__}
    epss_conn=next((x for x in connectors if x.get("kind")=="epss" and x.get("enabled",True) and profile in (x.get("profiles") or [])),None)
    if epss_conn:
        scores,s=epss_scores(epss_conn,[x.get("cve") for x in rows],timeout=timeout);stats[str(epss_conn.get("id"))]=s
        for r in rows:
            key=str(r.get("cve") or "").upper()
            if key in scores:r["epss"]=scores[key]
    if (config.get("generic_feed") or {}).get("enabled",True):
        gf,s=generic_feeds(registry,entities,config,timeout=timeout,cap=source_cap,state_dir=state_dir,profile=profile);rows.extend(gf);stats["generic_feeds"]=s
    else:
        stats["generic_feeds"]={"attempted_sources":0,"successful_sources":0,"rows":0,"status":"disabled"}
    return rows,stats
