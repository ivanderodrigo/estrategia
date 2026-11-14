#!/usr/bin/env python3
"""Reassess every historical claim-source hit, not merely URL availability.

Only first-party textual evidence of a specific fact or partnership is promoted.
Generic indexes, unrelated vendors, cross-owner pages and editorial guesses
are retained as research leads instead. Every claim is assessed independently.
The input has been fetched by revalidate_historical_sources.py.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import json,re,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical

CHECKS=ROOT/"data/current/historical_source_checks.json"
REGISTRY=ROOT/"config/current/historical_semantic_verified.json"
REPORT=ROOT/"data/public/historical/current/semantic_claim_audit.json"

RELATION_FIELDS={
    "integrators":{"vendor_relations","manufacturer_relations","vendor_partnerships",
                   "partnerships","alliances","westcon_overlap","competitor_vendor_overlap"},
    "distributors":{"vendor_relations","linecard_remainder","westcon_overlap","competitor_vendor_overlap"},
}
OWN_CAPABILITY={
    "manufacturers":{"capabilities"},
    "distributors":{"services","capabilities","specializations","technology_domains","training",
                    "marketplace","logistics","financing","verticals","differential_capabilities"},
    "integrators":{"capabilities","specializations","services","technology_domains",
                   "technology_specializations","service_portfolio"},
    "clients_private":{"technology_signals","hiring_signals","technology_domains"},
}
NEGATIVE=("por validar","por investigar","pendiente","posible","señal derivada",
          "señal estructural","hipótesis","no acreditado","no verificado")

def owner_site(entity,url):
    host=(urlparse(url).hostname or "").lower()
    host=host.removeprefix("www.")
    # Exact host labels also resolve short company names without accepting a
    # substring such as SIA inside asia.example.com.
    compact=re.sub(r"[^a-z0-9]","",canonical(entity))
    if compact and compact in host.split("."):
        return True
    tokens=[t for t in canonical(entity).split() if len(t)>=4 and t not in
            {"group","grupo","global","services","technology","technologies","solutions",
             "espana","spain","portugal","security","consulting","company"}]
    host_flat=re.sub(r"[^a-z0-9]","",host)
    return any(re.sub(r"[^a-z0-9]","",t) in host_flat for t in tokens)

def classify(claim,url):
    section=str(claim.get("section") or "")
    field=str(claim.get("field") or "")
    value=str(claim.get("value") or "").strip()
    entity=str(claim.get("entity") or "").strip()
    excerpt=str(claim.get("source_context") or "").strip()
    if not entity or not value or not excerpt or len(value)>1200:
        return "INSUFFICIENT_EXCERPT"
    clean=canonical(value)
    context=canonical(excerpt)
    if any(s in clean for s in NEGATIVE):
        return "HYPOTHESIS_NOT_FACT"
    semantic_short = (field in {"distributors", "competitors", "integrators"}
                      and section == "manufacturers") or field in OWN_CAPABILITY.get(section,set())
    if field not in RELATION_FIELDS.get(section,set()) and not semantic_short and (len(clean)<7 or len(clean.split())<2):
        return "AMBIGUOUS_SHORT_VALUE"
    # Archived analyst citations often paraphrase the headline. The
    # fetcher permits a strong local title-overlap only on the publication's
    # own domain, for citation fields and at least three distinctive words.
    publication_field = ((section, field) in {
        ("trends", "sources"), ("architectures", "analyst_basis")})
    publication_match = (publication_field
                         and claim.get("match_method") == "PUBLISHER_TITLE_OVERLAP"
                         and any(p in (urlparse(url).hostname or "").lower()
                                 and p in clean.split()[:3]
                                 for p in ("gartner", "forrester", "idc", "nist", "enisa")))
    if clean not in context and not publication_match:
        return "NOT_EXACT_IN_CONTEXT"
    direct_owner=owner_site(entity,url)
    article_names=canonical(entity) in context and len(canonical(entity))>=5
    # Explicit distribution announcements deserve atomic accreditation.
    # The two organisations must co-occur with a distribution-specific
    # statement on an official site belonging to either participant.
    # A generic channel/partner listing or a mere vendor mention is insufficient.
    if section=="manufacturers" and field=="distributors":
        official_party=direct_owner or owner_site(value,url)
        names_present=(direct_owner or canonical(entity) in context) and clean in context
        distribution_statement=any(term in context for term in (
            "distribution agreement", "distribution partnership",
            "distributor", "distribuidor", "distribucion",
            "distribuidores", "mayorista", "reseller agreement", "distribute",
        ))
        if official_party and names_present and distribution_statement:
            return "VERIFIED_EXPLICIT_DISTRIBUTION_AGREEMENT"
        return "DISTRIBUTION_RELATIONSHIP_NOT_SHOWN"
    if field in RELATION_FIELDS.get(section,set()):
        cues=("partner","alianza","alliance","ecosystem","fabricante","vendor","proveedor",
              "linecard","portfolio","catalogo","catalog","marcas","brands","distribu")
        page=canonical(urlparse(url).path)
        if (direct_owner or article_names) and (any(t in page for t in cues) or
               any(t in context for t in cues)):
            return "VERIFIED_EXPLICIT_PARTNER_CONTEXT"
        return "RELATIONSHIP_NOT_SHOWN"
    if section=="manufacturers" and field=="competitors":
        official_party = direct_owner or owner_site(value,url)
        # Official side-by-side vendor comparisons are explicit competitive
        # evidence even when the publisher calls them "X vs Y" rather than
        # using the literal English word "competitor".
        explicit_competition = any(cue in context for cue in (
            "competitor", "competition", "competes", "competidor",
            "alternative to", "alternativa a", "comparison", "compare to",
            "compare with", "comparativa", "comparacion",
        )) or bool(re.search(r"\\b(?:vs|versus)\\b", context))
        official_comparison_path = any(cue in canonical(urlparse(url).path) for cue in (
            "compare", "comparison", "comparativa", "versus", "alternatives",
        ))
        named_pair = canonical(entity) in context and clean in context
        page_path = canonical(urlparse(url).path)
        entity_name = canonical(entity)
        # A comparison page often contains unrelated vendor names in menus,
        # footers and "related comparisons". Credit ONLY the actual pair
        # identified by the source URL or an explicit "A vs B" phrase.
        if not official_party:
            return "COMPETITION_NOT_SHOWN"
        if official_comparison_path:
            direct_path_pair = (
                " vs " in f" {page_path} " and entity_name in page_path
                and clean in page_path
            )
            a, b = re.escape(entity_name), re.escape(clean)
            direct_text_pair = bool(re.search(
                rf"(?<![a-z0-9])(?:{a}\s+(?:vs|versus|contra)\s+{b}|"
                rf"{b}\s+(?:vs|versus|contra)\s+{a})(?![a-z0-9])",
                context,
            ))
            if not (direct_path_pair or direct_text_pair):
                return "COMPARISON_PAGE_DOES_NOT_NAME_PAIR"
        if official_party and (direct_owner or article_names) and named_pair and (
            explicit_competition or official_comparison_path
        ):
            return "VERIFIED_EXPLICIT_COMPETITOR_CONTEXT"
        return "COMPETITION_NOT_SHOWN"
    if field=="recent_signals" and direct_owner and len(clean.split())>=5:
        return "VERIFIED_FIRST_PARTY_NEWS_STATEMENT"
    if field=="public_cases" and direct_owner and len(clean.split())>=5 and any(
        cue in canonical(urlparse(url).path) for cue in ("case", "casos", "customer", "exito")
    ):
        return "VERIFIED_FIRST_PARTY_CASE_STUDY"
    if field in OWN_CAPABILITY.get(section,set()):
        if not direct_owner:
            return "NOT_FIRST_PARTY"
        # A corporate homepage that mentions a generic one-word industry
        # is not evidence that the company sells that named service.
        # E.g. Atos Spain -> "Logística" on an /es-es landing page.
        if field in {"services","capabilities","specializations"} and len(clean.split())==1 and len(clean)<12:
            path=canonical(urlparse(url).path).strip()
            if path in {"", "es", "es es", "pt", "pt pt", "en", "en us", "home", "inicio"}:
                return "GENERIC_HOMEPAGE_NOT_SERVICE_PROOF"
        if section=="clients_private":
            # A corporate source mentioning an exact, distinctive phrase proves
            # the owner's technology statement, but a short domain label does not.
            if field=="technology_signals" and len(clean)>=24 and len(clean.split())>=4:
                return "VERIFIED_FIRST_PARTY_TECH_STATEMENT"
            if field=="hiring_signals" and len(clean)>=13 and any(t in canonical(url) for t in ("job","career","emple","talent")):
                return "VERIFIED_FIRST_PARTY_HIRING"
            return "GENERIC_DOMAIN_OR_HIRING_NOT_SPECIFIC"
        if field=="differential_capabilities":
            if any(cue in clean for cue in ("mejor", "lider", "unico", "best", "leading", "unique")):
                return "DIFFERENTIAL_REQUIRES_COMPARISON"
            # A factual service or capacity does not assert superiority merely
            # because the UI places it in a differentiators column.
        if len(clean)<10 and field not in {"marketplace","financing","training"} and not any(
            cue in canonical(urlparse(url).path)+" "+context for cue in (
                "product", "solution", "solucion", "servic", "catalog", "portfolio", "ofrec", "offer"
            )
        ):
            return "GENERIC_CAPABILITY_NOT_SPECIFIC"
        return "VERIFIED_FIRST_PARTY_CATALOG_VALUE"
    if publication_field:
        report=(urlparse(url).hostname or "").lower()
        issuer=next((p for p in ("gartner","forrester","idc","nist","enisa")
                     if p in report and p in clean.split()[:3]), None)
        if issuer and len(clean)>=14 and (clean in context or publication_match):
            return "VERIFIED_CITED_ANALYST_DOCUMENT"
    return "UNSUPPORTED_FIELD_OR_CONTEXT"

def retained_comparison_is_still_explicit(old):
    """Re-evaluate legacy comparison-page proof under the exact-pair rule."""
    source = old.get("source") or {}
    if (old.get("section"),old.get("field")) != ("manufacturers","competitors"):
        return True
    if (source.get("source_type") != "historical-verified-excerpt"
        or source.get("verification_method") != "VERIFIED_EXPLICIT_COMPETITOR_CONTEXT"):
        return True
    url=str(source.get("url") or "")
    path=canonical(urlparse(url).path)
    if not any(term in path for term in (
        "compare","comparison","comparativa","versus","alternatives"
    )):
        return True
    description=str(source.get("description") or "")
    excerpt=description.split("Extracto de evidencia:",1)[-1].strip()
    candidate={"section":"manufacturers","field":"competitors",
               "entity":old.get("entity"),"value":old.get("value"),
               "source_context":excerpt}
    return classify(candidate,url)=="VERIFIED_EXPLICIT_COMPETITOR_CONTEXT"


def main():
    report=json.loads(CHECKS.read_text(encoding="utf-8"))
    results=report.get("results") or {}
    successes=[];review=[];seen=set();counter=Counter()
    for url,row in sorted(results.items()):
        for claim in row.get("claim_checks") or []:
            # When a linked official subpage proves the claim, cite that actual
            # page rather than the generic historical landing page.
            proof_url=str(claim.get("resolved_url") or url)
            status="SOURCE_UNAVAILABLE"
            if row.get("status") in ("REACHABLE_TEXT_MATCH","REACHABLE_NO_EXACT_TEXT"):
                if (
                    claim.get("status") == "VERIFIED_EXPLICIT_ALTERNATIVE"
                    and claim.get("accredited") is True
                    and claim.get("section") == "manufacturers"
                    and claim.get("field") == "competitors"
                    and urlparse(proof_url).hostname in {"www.gartner.com","gartner.com"}
                    and "/reviews/product/" in proof_url
                    and proof_url.rstrip("/").endswith("/alternatives")
                ):
                    status = "VERIFIED_EXPLICIT_ALTERNATIVE"
                elif claim.get("status")=="VALUE_PRESENT_REQUIRES_CONTEXT":
                    status=classify(claim,proof_url)
                else:
                    status="VALUE_NOT_FOUND"
            counter[status]+=1
            key=(claim.get("section"),claim.get("entity"),claim.get("field"),canonical(claim.get("value")),proof_url)
            if status.startswith("VERIFIED_") and key not in seen:
                seen.add(key)
                section,entity,field=claim["section"],claim["entity"],claim["field"]
                # Overlap is calculated from partnership + active portfolio.
                # Store the proven base relationship so rebuilds cannot erase
                # direct proof by regenerating the overlap column.
                if field in {"westcon_overlap", "competitor_vendor_overlap"}:
                    field = "vendor_relations"
                value=claim["value"]
                direct=owner_site(entity,proof_url)
                peer = status == "VERIFIED_EXPLICIT_ALTERNATIVE"
                source={
                    "url":proof_url,"source":"Gartner Peer Insights" if peer else
                             (entity if direct else urlparse(proof_url).hostname),
                    "title":(f"Alternativas explícitas a {entity} en Gartner Peer Insights" if peer
                             else f"Verificación de fuente histórica: {entity} / {field}"),
                    "description":(f"En la página de alternativas de producto a {entity}, "
                                   f"Gartner Peer Insights identifica expresamente a "
                                   f"{claim.get('matched_vendor')} como fabricante alternativo. "
                                   f"Extracto: {claim.get('source_context','')[:150]}"
                                   if peer else
                                   f"Extracto de evidencia: {claim.get('source_context','')[:260]}"),
                    "date":str(row.get("checked_at") or "")[:10],
                    "retrieved_at":str(row.get("checked_at") or "")[:10],
                    "provenance_origin":("PUBLIC_ANALYST" if peer else
                                         "PUBLIC_PRIMARY" if direct else "PUBLIC_SECONDARY"),
                    "source_type":"analyst-peer-review" if peer else "historical-verified-excerpt",
                    "verification_method":"explicit-product-alternative" if peer else status,
                    "classification":"public","source_grade":"B" if peer else ("A" if direct else "B"),
                    "source_binding":"claim-specific",
                    "freshness_status":"current",
                    "scope":"GLOBAL",
                    "official":False if peer else direct,
                }
                successes.append({"section":section,"entity":entity,"field":field,
                                  "value":value,"source":source})
            elif claim.get("status")=="VALUE_PRESENT_REQUIRES_CONTEXT":
                review.append({"section":claim.get("section"),"entity":claim.get("entity"),
                               "field":claim.get("field"),"value":claim.get("value"),
                               "url":proof_url,"historical_url":url,"reason":status})
    # A transient 403, timeout or JS-only source cannot disprove a relationship
    # that was already individually checked in an earlier run. Keep the last
    # successful proof available, with its actual verification date. Recheck
    # and expire after 120 days; never convert an unreachable URL into a *new*
    # accreditation.
    from datetime import date
    previous = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    old_records = list(previous.get("existing_claim_sources") or [])
    def signature(item):
        src=item.get("source") or {}
        return (item.get("section"),canonical(item.get("entity")),
                item.get("field"),canonical(item.get("value")),str(src.get("url") or ""))
    existing={signature(item) for item in successes}
    retained=0
    expired=0
    quarantined_legacy=0
    for old in old_records:
        # Previously retained positive matches must still satisfy the current
        # explicit-context policy. A generic corporate homepage does not
        # establish a one-word service, even if an old run once accepted it.
        oldsrc=old.get("source") or {}
        oldurl=str(oldsrc.get("url") or "")
        oldval=canonical(old.get("value") or "")
        oldfield=str(old.get("field") or "")
        oldpath=canonical(urlparse(oldurl).path)
        if (oldfield in {"services","capabilities","specializations"}
            and len(oldval.split())==1 and len(oldval)<12
            and oldpath in {"", "es", "es es", "pt", "pt pt", "en", "en us", "home", "inicio"}):
            quarantined_legacy+=1
            continue
        if not retained_comparison_is_still_explicit(old):
            quarantined_legacy+=1
            continue
        key=signature(old)
        if key in existing:
            continue
        src=old.get("source") or {}
        stamp=str(src.get("retrieved_at") or src.get("date") or "")[:10]
        try:
            age=(date.fromisoformat(str(report.get("generated_at") or "")[:10])-
                 date.fromisoformat(stamp)).days
        except ValueError:
            age=10_000
        if not (0<=age<=120):
            expired+=1
            continue
        preserved=json.loads(json.dumps(old,ensure_ascii=False))
        preserved["source"]["verification_reused"] = True
        preserved["source"]["verification_reuse_reason"] = (
            "Previously confirmed exact claim; latest fetch gave no new positive evidence"
        )
        successes.append(preserved)
        existing.add(key)
        retained+=1
    REGISTRY.parent.mkdir(parents=True,exist_ok=True)
    REGISTRY.write_text(json.dumps({"version":1,"generated_at":str(report.get("generated_at") or ""),
          "policy":"One-by-one first-party field/claim/source excerpt checks. Never authorizes historical archive mention alone.",
          "existing_claim_sources":successes},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({"generated_at":str(report.get("generated_at") or ""),
          "urls_scanned":len(results),"claim_source_pairs_reviewed":sum(counter.values()),
          "verified_claim_source_pairs":len(successes),
          "verified_this_run":len(successes)-retained,
          "retained_prior_verified":retained,
          "quarantined_generic_homepage_claims":quarantined_legacy,
          "expired_prior_verified":expired,
          "statuses":dict(counter),"by_section":dict(Counter(c["section"] for c in successes)),
          "pending_recheck_examples":review},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"urls_scanned":len(results),"claims_checked":sum(counter.values()),
          "verified":len(successes),"newly_verified":len(successes)-retained,
          "retained_prior_verified":retained,
          "by_section":dict(Counter(c["section"] for c in successes)),
          "statuses":dict(counter)},ensure_ascii=False))
    return successes

if __name__=="__main__":
    main()
