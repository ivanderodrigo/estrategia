#!/usr/bin/env python3
"""Bounded, repeated live checking of historical source leads.

A successful HTTP response or phrase hit is NOT sufficient to accredit an
atomic claim. Output is an auditable research queue, never accrediting evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.model import canonical
from engine.research.security import UnsafeUrl, validate_public_url
from engine.storage import atomic_write_json, read_json



class _HistoricalVisibleText(HTMLParser):
    """Include product and partner-logo alt labels lost by tag-stripping.

    An image's alt/aria-label text can be the only visible vendor name on an
    official partner directory. Scripts/styles never contribute claim evidence.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","noscript"}:
            self.skip += 1
            return
        if self.skip:
            return
        attributes = dict(attrs)
        for name in (("alt","aria-label","title") if tag in {"img","svg","a","button"} else ()):
            text = attributes.get(name)
            if text:
                self.parts.append(" " + text + " ")
        if tag == "meta" and str(attributes.get("name") or "").lower() in {"description","keywords"}:
            text = attributes.get("content")
            if text:
                self.parts.append(" " + text + " ")
        if tag in {"p","div","li","h1","h2","h3","h4","h5","tr","td","section"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script","style","noscript"} and self.skip:
            self.skip -= 1
        elif not self.skip and tag in {"p","div","li","h1","h2","h3","h4","h5","tr","td","section"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def historical_visible_text(html: str) -> str:
    parser = _HistoricalVisibleText()
    parser.feed(html)
    return canonical(unescape(" ".join(parser.parts)))


class _RelevantInternalLinks(HTMLParser):
    """Extract first-party product, partner and service links without crawling indiscriminately."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str,str]] = []
        self.current_href = ""
        self.current_label: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","noscript"}:
            self.skip += 1
            return
        if self.skip:
            return
        attributes = dict(attrs)
        if tag == "a" and not self.current_href:
            self.current_href = str(attributes.get("href") or "")
            self.current_label = [str(attributes.get("title") or ""),
                                  str(attributes.get("aria-label") or "")]
        if tag == "img" and self.current_href:
            self.current_label.append(str(attributes.get("alt") or ""))

    def handle_endtag(self, tag):
        if tag in {"script","style","noscript"} and self.skip:
            self.skip -= 1
        if tag == "a" and self.current_href:
            self.links.append((self.current_href, " ".join(self.current_label)))
            self.current_href = ""
            self.current_label = []

    def handle_data(self, data):
        if self.current_href and not self.skip:
            self.current_label.append(data)


def deep_source_links(html: str, base_url: str, *, limit: int = 4,
                      claims: list[dict] | None = None) -> list[str]:
    """Rank relevant same-host internal pages as next-hop source candidates."""
    from urllib.parse import urljoin
    parser = _RelevantInternalLinks()
    parser.feed(html[:1_000_000])
    base_host=(urlparse(base_url).hostname or "").lower().removeprefix("www.")
    ranked=[]
    seen=set()
    # Historical links are usually generic landing pages. Rank next-hop
    # sources by the actual unresolved manufacturer/value, not generic menu
    # labels that happen to say 'solutions' or 'services'.
    target_names={
        canonical(str(c.get("value") or "").split(" · ", 1)[0])
        for c in (claims or []) if len(canonical(c.get("value") or "")) >= 3
    }
    signals=("partner","fabricant","vendor","linecard","marcas","marca",
             "alianza","alliance","ecosystem","portfolio","catalog","product",
             "services","servicios","solutions","soluciones","customer","case",
             "casos","clientes","seguridad","security","network","cloud")
    for href,label in parser.links:
        if not href or href.startswith(("#","mailto:","tel:","javascript:")):
            continue
        resolved=urljoin(base_url,href)
        parsed=urlparse(resolved)
        if parsed.scheme!="https" or (parsed.hostname or "").lower().removeprefix("www.")!=base_host:
            continue
        clean=parsed._replace(fragment="",query="").geturl()
        if clean.rstrip("/")==base_url.split("?")[0].rstrip("/") or clean in seen:
            continue
        seen.add(clean)
        path=canonical(parsed.path)
        caption=canonical(label)
        path_hits=sum(sig in path for sig in signals)
        label_hits=sum(sig in caption for sig in signals)
        target_hits=sum(
            1 for name in target_names
            if name in (path+" "+caption)
            or name.replace(" ","-") in parsed.path.lower()
        )
        score=path_hits*3+label_hits*2+target_hits*12
        if score>0 and len(path)<180:
            ranked.append((-score,clean))
    ranked.sort()
    return [u for _,u in ranked[:limit]]


def historical_pdf_text(payload: bytes, *, max_pages: int = 120,
                        max_chars: int = 480_000) -> str:
    """Extract already selectable PDF text from official reports, without OCR.

    Avoid rendering or loading unbounded documents during a recurring crawl.
    Image-only or oversized PDFs remain research leads rather than proof.
    """
    if len(payload) > 12_000_000 or not payload.lstrip().startswith(b"%PDF"):
        return ""
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(payload), strict=False)
    if reader.is_encrypted:
        return ""
    parts: list[str] = []
    size = 0
    for page in reader.pages[:max_pages]:
        value = str(page.extract_text() or "")
        if not value:
            continue
        remaining = max_chars - size
        if remaining <= 0:
            break
        parts.append(value[:remaining])
        size += len(parts[-1])
    return canonical(" ".join(parts))



def best_claim_excerpt(text: str, value: str, field_id: str, *,
                       max_occurrences: int = 120) -> tuple[bool, str]:
    """Select the most probative local mention, not the first menu/SEO hit.

    Source text is already normalized. A contextual mention still requires a
    separate relationship classifier; this function never accredits itself.
    """
    if not value:
        return False, ""
    phrase = re.compile(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])")
    cues = {
        "distributors": ("distribution agreement", "distribution partnership",
                          "distributor", "distribuidor", "distribucion", "mayorista"),
        "vendor_relations": ("partner", "partnership", "alianza", "fabricante",
                             "vendors", "portfolio", "linecard"),
        "manufacturer_relations": ("partner", "fabricante", "portfolio", "alianza"),
        "vendor_partnerships": ("partner", "partnership", "alianza", "alliance"),
        "linecard_remainder": ("linecard", "fabricantes", "marcas", "vendors", "portfolio"),
        "competitors": ("competitor", "competition", "competes", "alternative",
                        "competidor", "rival", "versus"),
    }
    ranked = []
    for i, match in enumerate(phrase.finditer(text)):
        if i >= max_occurrences:
            break
        start, end = max(0, match.start()-220), min(len(text), match.end()+220)
        excerpt = text[start:end]
        words = cues.get(field_id, ())
        score = sum(4 for cue in words if cue in excerpt)
        score += sum(1 for cue in ("agreement", "announces", "signed", "official",
                                   "product", "services", "security", "solutions")
                     if cue in excerpt)
        # Prefer compact sentence-level proof over menu text if scores tie.
        ranked.append((score, -len(excerpt), -match.start(), excerpt))
    if not ranked:
        return False, ""
    return True, max(ranked)[-1]


# Publication citations are frequently abbreviated in older snapshots.
# Match a publisher-owned article by its distinctive title vocabulary, without
# requiring an exact editorial heading or crediting unrelated market claims.
CITATION_FIELDS = {("trends", "sources"), ("architectures", "analyst_basis")}
TITLE_STOPWORDS = {"the", "a", "an", "for", "and", "of", "in", "on", "to", "by",
                   "with", "from", "report", "study", "research", "market",
                   "global", "worldwide", "european", "2025", "2026", "2027",
                   "2028", "2029", "2030", "de", "del", "la", "el", "los",
                   "las", "en", "para", "y", "sobre", "un", "una"}
CITATION_PUBLISHERS = {"gartner", "forrester", "idc", "nist", "enisa"}

def publication_title_match(value: str, text: str, url: str, section: str,
                            field: str) -> tuple[bool, str]:
    if (section, field) not in CITATION_FIELDS:
        return False, ""
    host = (urlparse(url).hostname or "").lower()
    publisher = next((p for p in CITATION_PUBLISHERS
                      if p in canonical(value).split(" ")[:3]), None)
    if not publisher or publisher not in host:
        return False, ""
    title = canonical(value.split(":", 1)[-1].split("·", 1)[-1])
    words = [x for x in title.split() if x not in TITLE_STOPWORDS
             and len(x) >= 4]
    terms = set(words)
    # Short but distinctive publication titles can contain only two
    # meaningful tokens (e.g. "Cybersecurity Trends"). Do not require
    # a third token that the actual title does not contain.
    required = 2 if len(terms)==2 and any(len(t)>=10 for t in terms) else 3
    if len(terms) < required:
        return False, ""
    # A local passage, not global word presence across a site footer.
    passages = [text[max(0, m.start()-260):m.end()+260]
                for term in sorted(terms)[:5]
                for m in list(re.finditer(r"(?<![a-z0-9])" + re.escape(term) +
                         r"(?![a-z0-9])", text))[:20]]
    ranked = [(len({t for t in terms if re.search(
                  r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", part)}),
               part) for part in passages]
    if not ranked:
        return False, ""
    score, excerpt = max(ranked, key=lambda x: x[0])
    matched = score >= required and score / len(terms) >= .75
    return matched, excerpt if matched else ""

def candidate_inventory() -> dict[str, list[dict]]:
    targets: dict[str, list[dict]] = defaultdict(list)
    for section in ("manufacturers", "distributors", "integrators",
                    "trends", "architectures", "clients_private"):
        path = f"data/public/historical/current/{section}.json"
        store = read_json(path, {})
        for entity, fields in (store.get("entities") or {}).items():
            for field_id, claims in fields.items():
                for claim in claims:
                    value = claim.get("value")
                    if not isinstance(value, str):
                        continue  # Complex layer graphs need item-specific expert validation.
                    for url in claim.get("urls") or []:
                        if url.startswith("https://"):
                            targets[url].append({
                                "section": section, "entity": entity,
                                "field": field_id, "value": value,
                            })
    # Independently survey historical Git snapshots beyond the curated
    # sidecars. Archived evidence is never a proof by itself, but each exact
    # URL / entity / field / value tuple must enter the verification queue.
    recovered = read_json("data/public/historical/current/git_archive_additions.json", {})
    for claim in recovered.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        url = str(claim.get("url") or "")
        if not url.startswith("https://"):
            continue
        target = {k: claim.get(k) for k in ("section", "entity", "field", "value")}
        target["inventory_origin"] = "git-archive-recovered"
        if all(isinstance(target.get(k), str) and target[k].strip()
               for k in ("section", "entity", "field", "value")):
            if target not in targets[url]:
                targets[url].append(target)
    # The historical sidecars only describe gaps recovered from past revisions.
    # They are NOT the complete UI: surviving current field/item links are
    # invisible to that archive.  Check all exact, currently displayed items.
    current = read_json("data/current/intelligence.json", {})
    from engine.knowledge_provenance import accrediting_evidence
    for section in ("manufacturers", "distributors", "integrators",
                    "clients_public", "clients_private", "trends", "architectures"):
        for row in (current.get(section) or []):
            if not isinstance(row, dict):
                continue
            entity = str(row.get("name") or "").strip()
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict):
                    continue
                values = field.get("value")
                if isinstance(values, list):
                    candidates = [
                        (item.get("value"), list(item.get("evidence") or []))
                        for item in (field.get("items") or [])
                        if isinstance(item, dict)
                    ]
                    # If a UI list has no item objects, its field-wide
                    # references still need assessment per displayed value.
                    tracked = {canonical(v) for v, _ in candidates}
                    for value in values:
                        if isinstance(value, str) and canonical(value) not in tracked:
                            candidates.append((value, []))
                    # Legacy field-level evidence often applied to the whole
                    # list. Retain it as a lead for each exact item, not proof.
                    shared = list(field.get("evidence") or [])
                    candidates = [(v, ev + shared) for v, ev in candidates]
                else:
                    candidates = [(values, list(field.get("evidence") or []))]
                # Some older cards store source links at row level rather
                # than on the clicked competitor item. Those visible links
                # must still be investigated, but never automatically credited.
                if field_id in {
                    "competitors", "vendor_relations", "manufacturer_relations",
                    "vendor_partnerships", "alliances", "linecard_remainder",
                }:
                    fallback = list(row.get("evidence") or [])
                    candidates = [(v, ev + fallback) for v, ev in candidates]
                for value, evidences in candidates:
                    if not isinstance(value, str) or not value.strip():
                        continue
                    if any(
                        accrediting_evidence(ev)
                        and ev.get("atomic") is True
                        and str(ev.get("field") or "") == field_id
                        and canonical(ev.get("item_value")) == canonical(value)
                        for ev in evidences if isinstance(ev, dict)
                    ):
                        continue
                    for ev in evidences:
                        if not isinstance(ev, dict):
                            continue
                        url = str(ev.get("url") or "")
                        if not url.startswith("https://"):
                            continue
                        claim = {"section": section, "entity": entity,
                                 "field": field_id, "value": value,
                                 "inventory_origin": "current-visible-unaccredited"}
                        if claim not in targets[url]:
                            targets[url].append(claim)
    return targets


def check_one(url: str, claims: list[dict], timeout: float = 7.0,
              session: requests.Session | None = None, *, depth: int = 0) -> dict:
    checked = datetime.now(timezone.utc).isoformat()
    result = {"url": url, "checked_at": checked,
              "status": "UNAVAILABLE", "claim_hits": 0,
              "claims_tested": len(claims),
              "claim_checks": [{**claim, "status": "SOURCE_UNAVAILABLE",
                                "source_context": "", "accredited": False}
                               for claim in claims],
              "accreditation": "NOT_ACCREDITED"}
    try:
        safe = validate_public_url(url)
        get = session.get if session is not None else requests.get
        headers={"User-Agent": "Westcon-Intelligence-Historical-Revalidation/1.0"}
        redirects=[]
        # Redirects are not failed evidence: follow them only after validating
        # each next target against the public-URL security policy.
        for _ in range(4):
            response = get(safe, timeout=timeout, allow_redirects=False, headers=headers)
            if response.status_code not in (301,302,303,307,308):
                break
            from urllib.parse import urljoin
            location=response.headers.get("Location")
            if not location:
                break
            next_url=validate_public_url(urljoin(safe, location))
            redirects.append(next_url)
            safe=next_url
        result["http_status"] = response.status_code
        result["resolved_url"]=safe
        if redirects:
            result["redirect_chain"]=redirects
        if not (200 <= response.status_code < 300):
            result["status"] = "HTTP_UNAVAILABLE"
            return result
        content_type = str(response.headers.get("Content-Type") or "").lower()
        pdf_source = ("application/pdf" in content_type
                      or urlparse(safe).path.lower().endswith(".pdf"))
        if pdf_source:
            try:
                text = canonical(historical_pdf_text(response.content))
            except Exception as exc:
                result["status"] = "PDF_TEXT_EXTRACTION_FAILED"
                result["error_kind"] = type(exc).__name__
                return result
            result["source_format"] = "pdf"
        else:
            if content_type and not any(t in content_type for t in ("text/", "html", "json")):
                result["status"] = "NON_TEXT_SOURCE"
                return result
            text = historical_visible_text(response.text[:1_000_000])
            result["source_format"] = "html"
        if len(text) < 100:
            result["status"] = "INSUFFICIENT_SOURCE_CONTENT"
            return result
        # Every exact claim is evaluated separately. A text mention is a
        # RESEARCH FINDING, not accreditation: a vendor can occur in an index,
        # footnote, negative comparison or entirely unrelated page section.
        checks = []
        for claim in claims:
            raw_value = str(claim["value"])
            # A historical vendor-valued label may carry a market qualifier.
            # Example: "Huawei · Operations Support Systems peer". The page
            # calls the provider Huawei, not that entire editorial label.
            vendor = canonical(raw_value.split(" · ", 1)[0])
            qualifier = canonical(raw_value.split(" · ", 1)[1]) if " · " in raw_value else ""
            value = canonical(raw_value)
            field_id = str(claim.get("field") or "")
            is_gartner_alternative = bool(
                claim.get("section") == "manufacturers"
                and field_id == "competitors"
                and urlparse(safe).hostname in {"www.gartner.com", "gartner.com"}
                and re.fullmatch(r"/reviews/product/[a-z0-9-]+/alternatives/?", urlparse(safe).path)
                and canonical(claim.get("entity") or "").replace(" ", "-")
                   in urlparse(safe).path.split("/")[3]
            )
            # A top-level product-alternatives page explicitly identifies an
            # alternative manufacturer as "By <vendor>" in the same market.
            # This is stronger than a mere vendor mention in a generic report.
            explicit_alternative = False
            if is_gartner_alternative and vendor and len(vendor) >= 3:
                vendor_match = re.search(
                    r"(?<![a-z0-9])by\s+" + re.escape(vendor) + r"(?![a-z0-9])", text
                )
                has_market = (not qualifier or
                              all(x in text for x in qualifier.split()
                                  if x not in {"peer","competitor","rival"}))
                explicit_alternative = bool(vendor_match and has_market
                    and "alternatives" in text and "compare with" in text)
            tokens = value.split()
            # Short manufacturer names (F5, IBM, Cisco) are valid atomic
            # partner/linecard claims. Do not discard them simply because they
            # contain fewer than six characters. Restrict this expansion to a
            # vendor-relation field on an entity-owned public partner/linecard page.
            host = (urlparse(safe).hostname or "").lower().removeprefix("www.")
            owner_tokens = [t for t in canonical(claim.get("entity") or "").split()
                            if len(t)>=4 and t not in {
                                "group","grupo","technology","technologies","services",
                                "solutions","espana","portugal","spain","security",
                            }]
            owned = any(t.replace(" ","") in host.replace("-","")
                        for t in owner_tokens)
            partner_fields = {
                "vendor_relations","manufacturer_relations","vendor_partnerships",
                "partnerships","linecard_remainder","alliances",
            }
            partner_page = any(w in canonical(urlparse(safe).path) for w in (
                "partner","fabricante","vendor","alianza","alliance",
                "linecard","marcas","portfolio","catalogo"
            ))
            short_partner = bool(
                field_id in partner_fields and owned and partner_page
                and len(vendor) >= 2
            )
            informative = len(value) >= 2 and field_id in {
                "distributors", "competitors", "vendor_relations", "westcon_overlap",
                "manufacturer_relations", "vendor_partnerships", "partnerships",
                "linecard_remainder", "alliances", "competitor_vendor_overlap",
                "capabilities", "services", "specializations", "technology_domains",
                "market_players", "vendors",
            } or (
                (len(value) >= 6 and
                 (len(tokens) >= 2 or field_id in (
                    "competitors", "market_players", "vendors",
                    "vendor_relations", "westcon_overlap"
                 )))
                or short_partner
            )
            search_value = vendor if is_gartner_alternative else value
            occurs, context = (
                best_claim_excerpt(text, search_value, field_id)
                if informative else (False, "")
            )
            citation_match = False
            if not occurs:
                citation_match, citation_context = publication_title_match(
                    raw_value, text, safe, str(claim.get("section") or ""),
                    field_id)
                if citation_match:
                    occurs, context = True, citation_context
            checks.append({
                "match_method": "PUBLISHER_TITLE_OVERLAP" if citation_match else "EXACT_VALUE",
                "section": claim["section"], "entity": claim["entity"],
                "field": field_id, "value": raw_value[:1200],
                "status": ("VERIFIED_EXPLICIT_ALTERNATIVE" if explicit_alternative else
                           "VALUE_PRESENT_REQUIRES_CONTEXT" if occurs else
                           "NO_SPECIFIC_VALUE_CONFIRMED"),
                "source_context": context,
                "matched_vendor":vendor if explicit_alternative else None,
                "resolved_url": safe,
                "accredited": explicit_alternative,
            })
        hits = [c for c in checks if c["status"] in ("VALUE_PRESENT_REQUIRES_CONTEXT", "VERIFIED_EXPLICIT_ALTERNATIVE")]
        # A historical homepage often links to the *actual* partner catalogue
        # or services page. Follow a maximum of three same-host, semantically
        # relevant links, and only when the root URL belongs to the claimed
        # company. Each follow-up URL is individually SSRF-validated by check_one.
        if depth == 0 and result.get("source_format") == "html":
            host=(urlparse(safe).hostname or "").lower().removeprefix("www.")
            entities={canonical(c.get("entity") or "") for c in claims}
            owned_entities={e for e in entities if any(
                t in host.replace("-","") for t in e.split()
                if len(t)>=4 and t not in {"group","grupo","services","technology",
                                           "technologies","solutions","security",
                                           "espana","spain","portugal"}
            )}
            # A value mentioned on a homepage is not necessarily proof of the
            # claimed relationship. Inspect linked official catalogues even when
            # the homepage already mentions the vendor without enough context.
            unresolved=[c for c,check in zip(claims,checks)
                        if check["status"] in (
                            "NO_SPECIFIC_VALUE_CONFIRMED",
                            "VALUE_PRESENT_REQUIRES_CONTEXT",
                        )
                        and canonical(c.get("entity") or "") in owned_entities]
            if unresolved:
                deep_links=deep_source_links(response.text,safe,limit=4,claims=unresolved)
                result["followup_candidates"]=len(deep_links)
                result["deep_links_fetched"]=0
                result["deep_claim_hits"]=0
                for target in deep_links:
                    if not unresolved:
                        break
                    secondary=check_one(target,unresolved,timeout,
                                        session=session,depth=1)
                    result["deep_links_fetched"]+=1
                    if secondary.get("status") != "REACHABLE_TEXT_MATCH":
                        continue
                    found=[]
                    for claim,child in zip(unresolved,secondary.get("claim_checks") or []):
                        if child["status"] in (
                            "VALUE_PRESENT_REQUIRES_CONTEXT","VERIFIED_EXPLICIT_ALTERNATIVE"
                        ):
                            key=(claim["section"],claim["entity"],claim["field"],claim["value"])
                            for original in checks:
                                if (original["section"],original["entity"],original["field"],
                                    original["value"])==key:
                                    # A later menu mention must never replace an
                                    # already probative paragraph on the root page.
                                    from scripts.accredit_semantic_historical_sources import classify
                                    old_proven = classify(original, original.get("resolved_url") or safe).startswith("VERIFIED_")
                                    new_proven = classify(child, child.get("resolved_url") or target).startswith("VERIFIED_")
                                    if old_proven and not new_proven:
                                        continue
                                    original.update(child)
                                    original["discovered_from"]=url
                                    result["deep_claim_hits"]+=1
                                    if new_proven or child.get("accredited"):
                                        found.append(key)
                                    break
                    unresolved=[c for c in unresolved
                                if (c["section"],c["entity"],c["field"],c["value"]) not in found]
        hits = [c for c in checks if c["status"] in
                ("VALUE_PRESENT_REQUIRES_CONTEXT", "VERIFIED_EXPLICIT_ALTERNATIVE")]
        result["claim_checks"] = checks
        result["claim_hits"] = len(hits)
        result["semantically_verified"] = sum(c["status"] == "VERIFIED_EXPLICIT_ALTERNATIVE" for c in checks)
        result["examples"] = hits[:5]
        result["status"] = "REACHABLE_TEXT_MATCH" if hits else "REACHABLE_NO_EXACT_TEXT"
        return result
    except (requests.RequestException, ValueError, OSError, UnsafeUrl) as exc:
        result["status"] = "FETCH_ERROR"
        result["error_kind"] = type(exc).__name__
        return result


def run(limit: int, timeout: float, workers: int = 1) -> dict:
    inventory = candidate_inventory()
    previous = read_json("data/current/historical_source_checks.json", {})
    state = dict(previous.get("results") or {})
    # Oldest checked first; never treat repeated search failure as lack of relevance.
    ordered = sorted(inventory, key=lambda url: (str(state.get(url, {}).get("checked_at") or ""),
                                                   url))
    chosen = ordered[:max(1, limit)]
    stats = Counter()
    if workers <= 1:
        with requests.Session() as session:
            for url in chosen:
                outcome = check_one(url, inventory[url], timeout, session)
                state[url] = outcome
                stats[outcome["status"]] += 1
    else:
        # Limit concurrent requests to any one hostname (external courtesy).
        semaphores: dict[str, BoundedSemaphore] = {}
        mutex = Lock()
        def assess(url: str) -> tuple[str, dict]:
            host = urlparse(url).hostname or ""
            with mutex:
                if host not in semaphores:
                    semaphores[host] = BoundedSemaphore(2)
                semaphore = semaphores[host]
            with semaphore:
                return url, check_one(url, inventory[url], timeout)
        with ThreadPoolExecutor(max_workers=min(12, max(1, workers))) as pool:
            for url, outcome in pool.map(assess, chosen):
                state[url] = outcome
                stats[outcome["status"]] += 1
                completed_count = sum(stats.values())
                if completed_count % 50 == 0:
                    print(f"Historical audit: {completed_count}/{len(chosen)} URLs checked", flush=True)
    # Drop pages no longer referenced by any current historical assertion.
    state = {url: row for url, row in state.items() if url in inventory}
    completed = datetime.now(timezone.utc).isoformat()
    output = {
        "generated_at": completed,
        "status": "SOURCE_REACHABILITY_CHECK_NOT_ACCREDITATION",
        "urls_in_inventory": len(inventory),
        "urls_checked_this_run": len(chosen),
        "claims_checked_this_run": sum(int(state[url].get("claims_tested") or 0) for url in chosen),
        "urls_with_prior_checks": len(state),
        "claim_accuracy_note": "An HTTP success or phrase hit does not verify the specific fact; evidence promotion still needs content/relationship assessment.",
        "run_statuses": dict(stats),
        "results": state,
    }
    atomic_write_json("data/current/historical_source_checks.json", output)
    public = {k: value for k, value in output.items() if k != "results"}
    public["results"] = {url: {k: row.get(k) for k in (
        "checked_at", "status", "http_status", "claim_hits", "claims_tested", "accreditation")}
        for url, row in state.items()}
    atomic_write_json("data/public/historical/current/source_checks.json", public)
    print(json.dumps({k: v for k, v in output.items() if k != "results"},
                     ensure_ascii=False))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=7.0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    run(args.limit, args.timeout, args.workers)
