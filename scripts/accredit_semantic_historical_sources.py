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
                   "partnerships","alliances"},
    "distributors":{"vendor_relations","linecard_remainder"},
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
    if not entity or not value or not excerpt or len(value)>160:
        return "INSUFFICIENT_EXCERPT"
    clean=canonical(value)
    context=canonical(excerpt)
    if any(s in clean for s in NEGATIVE):
        return "HYPOTHESIS_NOT_FACT"
    if field not in RELATION_FIELDS.get(section,set()) and (len(clean)<7 or len(clean.split())<2):
        return "AMBIGUOUS_SHORT_VALUE"
    if clean not in context:
        return "NOT_EXACT_IN_CONTEXT"
    direct_owner=owner_site(entity,url)
    article_names=canonical(entity) in context and len(canonical(entity))>=5
    if field in RELATION_FIELDS.get(section,set()):
        cues=("partner","alianza","alliance","ecosystem","fabricante","vendor","proveedor")
        page=canonical(urlparse(url).path)
        if (direct_owner or article_names) and (any(t in page for t in cues) or
               any(t in context for t in cues)):
            return "VERIFIED_EXPLICIT_PARTNER_CONTEXT"
        return "RELATIONSHIP_NOT_SHOWN"
    if field in OWN_CAPABILITY.get(section,set()):
        if not direct_owner:
            return "NOT_FIRST_PARTY"
        if section=="clients_private":
            # A corporate source mentioning an exact, distinctive phrase proves
            # the owner's technology statement, but a short domain label does not.
            if field=="technology_signals" and len(clean)>=24 and len(clean.split())>=4:
                return "VERIFIED_FIRST_PARTY_TECH_STATEMENT"
            if field=="hiring_signals" and len(clean)>=13 and any(t in canonical(url) for t in ("job","career","emple","talent")):
                return "VERIFIED_FIRST_PARTY_HIRING"
            return "GENERIC_DOMAIN_OR_HIRING_NOT_SPECIFIC"
        if len(clean)<10 and field not in {"marketplace","financing","training"}:
            return "GENERIC_CAPABILITY_NOT_SPECIFIC"
        if field=="differential_capabilities":
            return "DIFFERENTIAL_REQUIRES_COMPARISON"
        return "VERIFIED_FIRST_PARTY_CATALOG_VALUE"
    if section=="architectures" and field=="analyst_basis":
        report=canonical(urlparse(url).hostname)
        if (("gartner" in report and "gartner" in clean) or
            ("forrester" in report and "forrester" in clean) or
            ("nist" in report and "nist" in clean) or
            ("enisa" in report and "enisa" in clean)) and len(clean)>=14:
            return "VERIFIED_CITED_ANALYST_DOCUMENT"
    if section=="trends" and field=="sources":
        report=canonical(urlparse(url).hostname)
        if (("gartner" in report and "gartner" in clean) or
            ("forrester" in report and "forrester" in clean) or
            ("nist" in report and "nist" in clean) or
            ("enisa" in report and "enisa" in clean)) and len(clean)>=14:
            return "VERIFIED_CITED_ANALYST_DOCUMENT"
    return "UNSUPPORTED_FIELD_OR_CONTEXT"

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
    REGISTRY.parent.mkdir(parents=True,exist_ok=True)
    REGISTRY.write_text(json.dumps({"version":1,"generated_at":str(report.get("generated_at") or ""),
          "policy":"One-by-one first-party field/claim/source excerpt checks. Never authorizes historical archive mention alone.",
          "existing_claim_sources":successes},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({"generated_at":str(report.get("generated_at") or ""),
          "urls_scanned":len(results),"claim_source_pairs_reviewed":sum(counter.values()),
          "verified_claim_source_pairs":len(successes),
          "statuses":dict(counter),"by_section":dict(Counter(c["section"] for c in successes)),
          "pending_recheck_examples":review[:250]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"urls_scanned":len(results),"claims_checked":sum(counter.values()),
          "verified":len(successes),"by_section":dict(Counter(c["section"] for c in successes)),
          "statuses":dict(counter)},ensure_ascii=False))
    return successes

if __name__=="__main__":
    main()
