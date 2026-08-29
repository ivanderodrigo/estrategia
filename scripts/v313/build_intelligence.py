#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from v313.gap_engine import build_gaps

ROOT = Path(__file__).resolve().parents[2]

from v38.build_intelligence import atomic_item, dedupe_evidence, evidence, field, load, write
from v39.build_intelligence import build as build_v39, merge_source_catalog as merge_source_catalog_v39

VERSION = "3.13.0"


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


ALIASES = {
    "v valley esprinet": "esprinet",
    "esprinet v valley": "esprinet",
    "v valley advanced solutions portugal": "esprinet",
    "esprinet": "esprinet",
    "td synnex portugal": "td synnex",
    "also portugal": "also",
    "arrow ecs portugal": "arrow ecs",
    "exclusive networks portugal": "exclusive networks",
    "infinigate portugal": "infinigate",
    "ingram micro portugal": "ingram micro",
    "mcr portugal": "mcr",
    "ignition portugal": "ignition technology",
    "tata consultancy services tcs": "tata consultancy services",
    "tcs": "tata consultancy services",
    "orange business spain": "orange business",
    "t systems itc iberia": "t systems iberia",
    "t systems spain": "t systems iberia",
    "seidor": "seidor",
    "inetum spain": "inetum",
    "ntt data spain": "ntt data",
}


def canonical(value: Any) -> str:
    key = norm(value)
    return ALIASES.get(key, key)


def ev_obj(raw: dict[str, Any]) -> dict[str, Any]:
    item = evidence(raw)
    return item or raw


def merge_source_catalog() -> list[dict[str, Any]]:
    rows = {x.get("id"): dict(x) for x in merge_source_catalog_v39() if x.get("id")}
    for raw in load("config/v313/source_additions.json", {}).get("sources", []) or []:
        sid = raw.get("source_id") or raw.get("id")
        if not sid:
            continue
        rows[sid] = {
            "id": sid,
            "name": raw.get("name"),
            "url": raw.get("url"),
            "class": raw.get("source_class") or raw.get("class"),
            "scope": raw.get("scope") or [],
            "dimensions": raw.get("dimensions") or [],
            "access_policy": raw.get("access_policy") or "public",
        }
    return sorted(rows.values(), key=lambda x: (str(x.get("class") or ""), str(x.get("name") or "")))


def _ensure_schema(data: dict[str, Any], section: str, additions: list[dict[str, Any]], prepend: bool = True) -> None:
    current = list((data.get("schemas") or {}).get(section) or [])
    ids = {x.get("id") for x in current}
    fresh = [x for x in additions if x.get("id") not in ids]
    data.setdefault("schemas", {})[section] = ([*fresh, *current] if prepend else [*current, *fresh])


def _field_value(row: dict[str, Any], fid: str) -> Any:
    spec = (row.get("fields") or {}).get(fid) or {}
    return spec.get("value")


def _field_evidence(row: dict[str, Any], fid: str) -> list[dict[str, Any]]:
    spec = (row.get("fields") or {}).get(fid) or {}
    return list(spec.get("evidence") or [])


def _merge_field_list(row: dict[str, Any], fid: str, label: str, ev: dict[str, Any], confidence: float = .96) -> None:
    fields = row.setdefault("fields", {})
    old = fields.get(fid) or {}
    values = old.get("value") or []
    if not isinstance(values, list):
        values = [values]
    # Relation identity is the name before middle dot.
    head = canonical(str(label).split("·", 1)[0])
    if not any(canonical(str(v).split("·", 1)[0]) == head for v in values):
        values.append(label)
    items = list(old.get("items") or [])
    if not any(canonical(str(x.get("value", "")).split("·", 1)[0]) == head for x in items):
        atom = atomic_item(label, [ev], confidence)
        if atom:
            items.append(atom)
    all_ev = dedupe_evidence([*(old.get("evidence") or []), ev], 12)
    built = field(values, all_ev, max(float(old.get("confidence") or 0), confidence), old.get("qualifier"), items=items)
    if built:
        fields[fid] = built


def validate_distributors(data: dict[str, Any]) -> dict[str, Any]:
    registry = load("config/v313/distributor_registry.json", {})
    entries = registry.get("entries") or []
    false_terms = [norm(x) for x in (registry.get("policy") or {}).get("vendor_false_positive_terms", [])]
    manufacturer_keys = {canonical(r.get("name")) for r in data.get("manufacturers", []) if r.get("name")}
    internal = {"westcon", "comstor", "westcon comstor"}

    by_alias: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for label in [entry.get("name"), *(entry.get("aliases") or [])]:
            if label:
                by_alias[canonical(label)] = entry

    existing_by_key = {canonical(r.get("name")): r for r in data.get("distributors", []) if r.get("name")}
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    removed_vendor_like: list[str] = []
    removed_unvalidated: list[str] = []

    # Start from the positive registry. Existing intelligence is merged when present.
    for entry in entries:
        key = canonical(entry.get("name"))
        # Never publish known/internal vendor brands as competitor wholesalers.
        if key in internal or key in manufacturer_keys or any(term and term in key for term in false_terms):
            continue
        # Find an existing row by canonical name or any registry alias.
        candidates = [key, *[canonical(x) for x in entry.get("aliases") or []]]
        base = next((copy.deepcopy(existing_by_key[x]) for x in candidates if x in existing_by_key), None)
        if base is None:
            base = {"id": f"dist-v313-{len(output)+1:03d}", "name": entry.get("name"), "evidence": [], "fields": {}}
        base["name"] = entry.get("name")
        evs = [ev_obj(x) for x in entry.get("validation_evidence") or []]
        base["evidence"] = dedupe_evidence([*(base.get("evidence") or []), *evs], 12)
        scopes = entry.get("scope") or []
        scope_val = " + ".join(scopes)
        if scope_val:
            base.setdefault("fields", {})["scope"] = field(scope_val, evs, .96, "Ámbito respaldado por la fuente que valida a la entidad como distribuidor/mayorista.")
        base["fields"]["distributor_type"] = field(entry.get("type") or "Distribuidor tecnológico", evs, .96, "Tipología descriptiva del modelo de distribución, no ranking competitivo.")
        base["fields"]["validation_status"] = field("Mayorista / distribuidor validado", evs, .98, "La entidad entra en Mayoristas porque existe evidencia positiva explícita de distribución; no por coaparición con fabricantes.")
        if entry.get("rank"):
            base["fields"]["market_position"] = field(f"#{entry['rank']} España · facturación 2025", evs, .97, "Posición en el adelanto del Ranking del Canal 2026 de Channel Partner, basado en facturación 2025.")
        output.append(base)
        seen.add(key)

    # Audit all legacy rows, explicitly documenting why they no longer pass the gate.
    for row in data.get("distributors", []) or []:
        key = canonical(row.get("name"))
        if key in seen:
            continue
        if key in manufacturer_keys or any(term and term in key for term in false_terms):
            removed_vendor_like.append(row.get("name"))
        elif key not in by_alias:
            removed_unvalidated.append(row.get("name"))

    data["distributors"] = sorted(output, key=lambda r: norm(r.get("name")))
    return {
        "policy": "positive-validation-first",
        "validated_distributors": len(output),
        "removed_vendor_like": sorted(set(x for x in removed_vendor_like if x)),
        "removed_unvalidated": sorted(set(x for x in removed_unvalidated if x)),
        "registry_entries": len(entries),
    }


def _sanitize_fit_field(row: dict[str, Any], allowed: dict[str, str]) -> int:
    fields = row.get("fields") or {}
    spec = fields.get("westcon_fit")
    if not spec:
        return 0
    values = spec.get("value") or []
    if not isinstance(values, list):
        values = [values]
    kept: list[str] = []
    removed = 0
    for value in values:
        key = canonical(str(value).split("·", 1)[0])
        if key in allowed:
            kept.append(allowed[key])
        else:
            removed += 1
    if not kept:
        fields.pop("westcon_fit", None)
        return removed
    # Retain only atomic items/evidence that match surviving values when possible.
    items = [x for x in spec.get("items") or [] if canonical(str(x.get("value", "")).split("·", 1)[0]) in allowed]
    evs = list(spec.get("evidence") or [])
    rebuilt = field(kept, evs, spec.get("confidence"), spec.get("qualifier"), items=items or None)
    if rebuilt:
        fields["westcon_fit"] = rebuilt
    else:
        fields.pop("westcon_fit", None)
    return removed


def sanitize_westcon_fit(data: dict[str, Any]) -> dict[str, int]:
    # The active manufacturer dataset is the only admissible source of portfolio names.
    allowed = {canonical(r.get("name")): r.get("name") for r in data.get("manufacturers", []) if r.get("name")}
    aliases = {
        "amazon web services": "AWS",
        "aws": "AWS",
        "azure": "Microsoft Azure",
        "microsoft": "Microsoft Azure",
        "akamai": "Akamai / Noname",
        "noname": "Akamai / Noname",
    }
    for alias, target in aliases.items():
        tkey = canonical(target)
        if tkey in allowed:
            allowed[canonical(alias)] = allowed[tkey]
    removed_public = sum(_sanitize_fit_field(r, allowed) for r in data.get("clients_public", []) or [])
    removed_private = sum(_sanitize_fit_field(r, allowed) for r in data.get("clients_private", []) or [])
    return {"removed_nonportfolio_public": removed_public, "removed_nonportfolio_private": removed_private, "allowed_portfolio_names": len({v for v in allowed.values()})}


def build_private_accounts(data: dict[str, Any]) -> dict[str, int]:
    universe = load("config/v313/private_account_universe.json", {}).get("accounts") or []
    existing = {canonical(r.get("name")): copy.deepcopy(r) for r in data.get("clients_private", []) if r.get("name")}
    # Common-name aliases between seed and index.
    alias_existing = {
        "banco santander": "banco santander",
        "santander": "banco santander",
        "galp energia": "galp",
        "jeronimo martins": "jeronimo martins",
    }
    rows=[]
    for idx,acc in enumerate(universe,1):
        key=canonical(acc.get("name")); candidates=[key]
        if key in alias_existing: candidates.append(alias_existing[key])
        if key=="banco santander": candidates.append("santander")
        if key=="galp energia": candidates.append("galp")
        row=next((copy.deepcopy(existing[c]) for c in candidates if c in existing),None)
        ev=ev_obj(acc.get("evidence") or {})
        if row is None:
            row={"id":f"priv-v313-{idx:03d}","name":acc.get("name"),"evidence":[ev],"fields":{}}
        else:
            row["name"]=acc.get("name")
            row["evidence"]=dedupe_evidence([*(row.get("evidence") or []),ev],12)
        fields=row.setdefault("fields",{})
        fields["scope"]=field(acc.get("scope"),[ev],.98,"País de referencia del índice bursátil usado para definir el universo mínimo de grandes cuentas.")
        fields["index_universe"]=field(acc.get("index"),[ev],.98,"Pertenencia al índice oficial; sirve para garantizar cobertura estructural mínima de grandes cuentas, no para priorizar inversión.")
        # Preserve richer existing segment when present.
        if not fields.get("segment"):
            fields["segment"]=field(acc.get("segment"),[ev],.92,"Sector descriptivo de la gran cuenta.")
        fields["account_priority"]=field(f"Cobertura estructural · {acc.get('index')}",[ev],.96,"La cuenta se incluye por pertenecer al universo mínimo solicitado (IBEX 35 o PSI); no es una recomendación comercial.")
        rows.append(row)
    data["clients_private"]=rows
    return {"ibex35":sum(1 for x in universe if x.get("index")=="IBEX 35"),"psi":sum(1 for x in universe if x.get("index")=="PSI"),"total":len(rows)}


def build_public_procurement(data: dict[str, Any]) -> dict[str, int]:
    snapshot = load("config/v313/procurement_snapshot.json", {}).get("notices") or []
    live = load("data/v313/procurement_live.json", {}).get("notices") or []
    merged: dict[str, dict[str, Any]] = {}
    for item in [*snapshot, *live]:
        notice=str(item.get("notice_id") or "").strip()
        url=str(item.get("url") or "").strip()
        portal=str(item.get("source_portal") or ("TED" if "ted.europa.eu" in url else "PLACSP" if "contrataciondelestado" in url or "contrataciondelsectorpublico" in url else "")).strip()
        exact_ted="ted.europa.eu" in url and "/notice/-/detail/" in url
        exact_placsp=portal.upper()=="PLACSP" and ("contrataciondelestado" in url or "contrataciondelsectorpublico" in url) and "http" in url
        if not notice or not url or not (exact_ted or exact_placsp):
            continue
        item=dict(item); item["source_portal"]=portal or "TED"
        merged[f"{item['source_portal']}:{notice}"]=item
    rows=[]
    for idx,item in enumerate(sorted(merged.values(),key=lambda x:(str(x.get("date") or ""),str(x.get("notice_id") or "")),reverse=True),1):
        notice=item.get("notice_id"); scope=item.get("scope") or "—"; portal=item.get("source_portal") or "TED"; title=item.get("title") or f"Anuncio {portal} {notice}"; buyer=item.get("buyer") or f"Organismo público · {scope}"
        ev=ev_obj({
            "source":item.get("source") or ("TED · Tenders Electronic Daily" if portal=="TED" else "PLACSP · Plataforma de Contratación del Sector Público"),
            "title":f"{notice} · {title}",
            "description":title,
            "url":item.get("url"),
            "date":item.get("date") or "2026",
            "source_type":"official-procurement-notice",
            "source_grade":"A",
            "confidence":item.get("confidence") or .94,
            "scope":scope,
        })
        fields={
            "notice_id":field(notice,[ev],.99,"Identificador exacto del anuncio. El enlace de Información abre el anuncio concreto, no la portada del portal."),
            "source_portal":field(f"{portal} · anuncio/expediente exacto",[ev],.99,"Portal oficial y enlace directo del anuncio o expediente; no una portada genérica."),
            "scope":field(scope,[ev],.98,"País indicado por el anuncio oficial."),
            "entity_type":field("Organismo / entidad pública",[ev],.91,"Clasificación conservadora; el anuncio exacto contiene la identidad formal del comprador cuando está disponible."),
            "request_or_need":field(title,[ev],.96,"Objeto/necesidad tomada del anuncio público concreto."),
            "opportunity_area":field(item.get("area") or "Tecnología / servicios TI",[ev],.91,"Área tecnológica descriptiva derivada del objeto del anuncio."),
            "procurement_stage":field(f"Anuncio oficial publicado · {portal}",[ev],.96,"Existe un anuncio/expediente oficial publicado; el estado detallado debe leerse en el enlace concreto."),
            "milestone_date":field(str(item.get("date") or f"2026 · {notice}"),[ev],.90,"Referencia temporal tomada de la fuente oficial cuando está disponible."),
            "technology_signals":field([x.strip() for x in str(item.get("area") or "Tecnología").split("/")],[ev],.89,"Señales funcionales derivadas del objeto del expediente, no adjudicación ni fabricante confirmado."),
            "opportunity_notes":field("Oportunidad pública trazable a expediente concreto. Revisar el anuncio oficial para plazos, lotes, importe y documentación vigente.",[ev],.94,"Lectura operativa descriptiva; no presupone encaje comercial ni adjudicación."),
        }
        # Exact amounts only where a detailed notice supplied an explicit value.
        known_amounts={"105593-2026":"3.445.000 EUR estimados","67886-2026":"1.000.000 EUR estimados","141955-2026":"600.000 EUR"}
        if notice in known_amounts:
            fields["estimated_amount"]=field(known_amounts[notice],[ev],.96,"Importe observado en el anuncio TED detallado.")
        fields={k:v for k,v in fields.items() if v}
        rows.append({"id":f"pub-v313-{idx:03d}","name":buyer,"evidence":[ev],"fields":fields})
    data["clients_public"]=rows
    return {"exact_notices":len(rows),"live_notices":len(live),"snapshot_notices":len(snapshot)}


def ensure_integrator(row_map: dict[str, dict[str, Any]], name: str, scope: str, role: str, ev: dict[str, Any], idx: int) -> dict[str, Any]:
    key=canonical(name)
    row=row_map.get(key)
    if row is None:
        row={"id":f"integrator-v313-{idx:03d}","name":name,"evidence":[ev],"fields":{}}
        row_map[key]=row
    else:
        row["evidence"]=dedupe_evidence([*(row.get("evidence") or []),ev],12)
    fields=row.setdefault("fields",{})
    if not fields.get("scope"):
        fields["scope"]=field(scope,[ev],.90,"Ámbito explícito de la evidencia añadida por v3.13; GLOBAL no implica presencia Iberia.")
    # Merge role rather than overwrite existing taxonomy.
    roles=fields.get("roles") or {}
    vals=roles.get("value") or []
    if not isinstance(vals,list): vals=[vals]
    if role not in vals: vals.append(role)
    role_ev=dedupe_evidence([*(roles.get("evidence") or []),ev],12)
    built=field(vals,role_ev,max(float(roles.get("confidence") or 0),.91),"Roles observados en fuentes públicas; no todos implican el mismo nivel de certificación.")
    if built: fields["roles"]=built
    return row


def expand_integrator_graph(data: dict[str, Any]) -> dict[str, Any]:
    universe=load("config/v313/integrator_universe.json",{})
    universe_ev=ev_obj(universe.get("source") or {})
    row_map={canonical(r.get("name")):copy.deepcopy(r) for r in data.get("integrators",[]) if r.get("name")}
    # Add missing top-universe integrators without inventing vendor relationships.
    next_idx=1
    for name in universe.get("entities") or []:
        key=canonical(name)
        if key in row_map: continue
        scope="ES" if name in {'Indra','Accenture Spain','NTT Data Spain','Seidor','Inetum','Ayesa','Kyndryl','Capgemini Spain','DXC Technology Spain','Econocom Spain','GMV','Making Science','Evolutio','VASS','T-Systems Iberia'} else "GLOBAL"
        ensure_integrator(row_map,name,scope,"Integrador / consultora TI" if scope=='ES' else "Integrador / service partner",universe_ev,next_idx); next_idx+=1

    manufacturers={canonical(r.get("name")):r for r in data.get("manufacturers",[]) if r.get("name")}
    rels=load("config/v313/curated_integrator_relations.json",{}).get("relations") or []
    added=0
    for rel in rels:
        vkey=canonical(rel.get("vendor")); manufacturer=manufacturers.get(vkey)
        if not manufacturer: continue
        ev=ev_obj(rel.get("evidence") or {})
        integrator=ensure_integrator(row_map,rel.get("integrator"),rel.get("scope") or 'GLOBAL',rel.get("role") or 'Partner / integrator',ev,next_idx); next_idx+=1
        # Vendor -> integrator
        before=list((_field_value(manufacturer,"integrators") or []))
        label=f"{integrator.get('name')} · {rel.get('scope') or 'GLOBAL'} · Evidencia oficial"
        _merge_field_list(manufacturer,"integrators",label,ev,float((rel.get('evidence') or {}).get('confidence') or .94))
        after=list((_field_value(manufacturer,"integrators") or []))
        if len(after)>len(before): added+=1
        # Integrator -> vendor
        _merge_field_list(integrator,"vendor_relations",f"{manufacturer.get('name')} · Confirmada · {rel.get('scope') or 'GLOBAL'}",ev,float((rel.get('evidence') or {}).get('confidence') or .94))

    data["integrators"]=sorted(row_map.values(),key=lambda r:norm(r.get("name")))
    # Graph coverage is calculated from both directions after dedupe.
    vendor_counts=[]
    edge_keys=set()
    for m in data.get("manufacturers",[]):
        vals=_field_value(m,"integrators") or []
        if not isinstance(vals,list): vals=[vals]
        heads={canonical(str(v).split('·',1)[0]) for v in vals if v}
        vendor_counts.append((m.get('name'),len(heads)))
        for h in heads: edge_keys.add((canonical(m.get('name')),h))
    integ_counts=[]
    for i in data.get("integrators",[]):
        vals=_field_value(i,"vendor_relations") or []
        if not isinstance(vals,list): vals=[vals]
        integ_counts.append((i.get('name'),len({canonical(str(v).split('·',1)[0]) for v in vals if v})))
    avg_vendor=round(sum(x[1] for x in vendor_counts)/max(1,len(vendor_counts)),2)
    avg_integrator=round(sum(x[1] for x in integ_counts)/max(1,len(integ_counts)),2)
    return {
        "curated_relations_considered":len(rels),"new_vendor_integrator_edges":added,"unique_vendor_integrator_edges":len(edge_keys),
        "avg_integrators_per_manufacturer":avg_vendor,"avg_vendors_per_integrator":avg_integrator,
        "manufacturers_below_3_integrators":[name for name,count in vendor_counts if count<3],
        "manufacturers_without_integrators":[name for name,count in vendor_counts if count==0],
        "integrators":len(data.get("integrators",[])),
    }



PROFILE_TAXONOMY = {
    "services": {
        "Managed Services": ["managed service", "managed-services"],
        "Servicios profesionales / consultoría": ["professional service", "consulting", "consultoria", "consultoría"],
        "Implementación e integración": ["implementation", "integration service", "integracion", "integración"],
        "Soporte": ["support service", "support", "soporte"],
        "Formación / enablement": ["training", "academy", "formacion", "formación"],
        "Marketplace / cloud commerce": ["marketplace", "cloud commerce"],
    },
    "capabilities": {
        "Ciberseguridad": ["cybersecurity", "cyber security", "ciberseguridad", "security service"],
        "Networking": ["networking", "network service", "network infrastructure"],
        "Cloud": ["cloud migration", "cloud service", "public cloud", "hybrid cloud"],
        "SOC": [" soc ", "security operations center", "security operations centre"],
        "NOC": [" noc ", "network operations center", "network operations centre"],
        "MSSP": ["mssp"],
        "MSP": ["msp", "managed service provider"],
        "Observabilidad": ["observability", "monitoring"],
        "Automatización / IA": ["automation", "artificial intelligence", " ai ", "automatizacion", "automatización"],
        "Data Center": ["data center", "datacenter"],
        "Identidad": ["identity", "iam"],
        "OT / IoT": ["ot security", "operational technology", "iot"],
    },
    "verticals": {
        "Servicios financieros": ["financial services", "banking", "finance"],
        "Sector público": ["public sector", "government", "administracion publica", "administración pública"],
        "Sanidad": ["healthcare", "health sector"],
        "Retail": ["retail"],
        "Industria": ["industrial", "manufacturing"],
        "Energía / utilities": ["energy", "utilities"],
        "Telecomunicaciones": ["telecom", "telco"],
        "Transporte": ["transport", "mobility"],
        "Educación": ["education", "university"],
    },
    "job_profiles": {
        "Security Engineer / Analyst": ["security engineer", "security analyst", "soc analyst"],
        "Network Engineer": ["network engineer"],
        "Cloud Engineer / Architect": ["cloud engineer", "cloud architect"],
        "Solution Architect": ["solution architect", "solutions architect"],
        "Consultoría": ["consultant", "consultor"],
        "Preventa": ["presales", "pre-sales", "preventa"],
    },
}

def _research_blob(ev: dict[str, Any]) -> str:
    return norm(" ".join(str(ev.get(k) or "") for k in ("title","snippet","summary","url","headings")))

def _labels_from_taxonomy(ev: dict[str, Any], dimension: str) -> list[str]:
    blob = f" {_research_blob(ev)} "
    labels=[]
    for label, terms in PROFILE_TAXONOMY.get(dimension, {}).items():
        if any(norm(term) in blob for term in terms): labels.append(label)
    return labels

def enrich_entity_profiles(data: dict[str, Any]) -> dict[str, Any]:
    """Promote official entity-profile evidence gathered by the research engine.

    Crucially, jobs can fill job fields but never create a partner relationship.
    Partner/vendor edges require a vendor mention on a non-job official entity page.
    """
    research=load('data/research.latest.json',{})
    evidence_rows=research.get('evidence') or []
    manufacturer_by_key={canonical(r.get('name')):r for r in data.get('manufacturers',[]) if r.get('name')}
    stats={'official_profile_evidence':0,'integrator_fields_enriched':0,'distributor_fields_enriched':0,'relationship_edges_promoted':0}
    sections={'integrator':'integrators','distributor':'distributors'}
    for kind,section in sections.items():
        rows={canonical(r.get('name')):r for r in data.get(section,[]) if r.get('name')}
        for raw in evidence_rows:
            if raw.get('entityKind') != kind or not raw.get('sourceEntity'): continue
            row=rows.get(canonical(raw.get('sourceEntity')));
            if not row: continue
            tier=norm(raw.get('sourceTier')); engine=norm(raw.get('engine'))
            if tier not in {'official company','official-company'} and 'official ecosystem sitemap' not in engine: continue
            ev=ev_obj(raw); dims=set(raw.get('profileDimensions') or []); stats['official_profile_evidence']+=1
            touched=set()
            for dim in ('services','capabilities','verticals','job_profiles'):
                if dim not in dims: continue
                for label in _labels_from_taxonomy(raw,dim):
                    _merge_field_list(row,dim,label,ev,.86 if dim!='job_profiles' else .72); touched.add(dim)
            if 'public_cases' in dims:
                title=str(raw.get('title') or '').strip()
                if title and len(title)>8:
                    _merge_field_list(row,'public_cases',title[:160],ev,.84); touched.add('public_cases')
            if 'specializations' in dims:
                title=str(raw.get('title') or '').strip()
                if title and len(title)>8:
                    _merge_field_list(row,'specializations',title[:150],ev,.82); touched.add('specializations')
            # Employment pages are valuable for technology demand, but never prove partnership.
            if 'job_profiles' in dims:
                blob=_research_blob(raw)
                for m in data.get('manufacturers',[]):
                    mname=str(m.get('name') or ''); aliases=[canonical(mname), canonical(mname.split('/',1)[0])]
                    if any(a and len(a)>=3 and a in blob for a in aliases):
                        _merge_field_list(row,'job_vendors',f"{mname} · señal de empleo",ev,.62); touched.add('job_vendors')
            vendor=raw.get('vendor')
            if vendor and 'job_profiles' not in dims:
                m=manufacturer_by_key.get(canonical(vendor))
                if m:
                    if kind=='integrator':
                        before=len(_field_value(row,'vendor_relations') or [])
                        _merge_field_list(row,'vendor_relations',f"{m.get('name')} · evidencia oficial",ev,.90)
                        _merge_field_list(m,'integrators',f"{row.get('name')} · evidencia oficial",ev,.90)
                        if len(_field_value(row,'vendor_relations') or [])>before: stats['relationship_edges_promoted']+=1
                        touched.add('vendor_relations')
                    else:
                        before=len(_field_value(row,'vendor_relations') or [])
                        _merge_field_list(row,'vendor_relations',f"{m.get('name')} · portfolio oficial",ev,.90)
                        if len(_field_value(row,'vendor_relations') or [])>before: stats['relationship_edges_promoted']+=1
                        touched.add('vendor_relations')
            stats[f'{kind}_fields_enriched']+=len(touched)
        # Distributor overlap is a derived intersection of validated vendor relations and active Westcon portfolio.
        if kind=='distributor':
            for row in rows.values():
                rels=_field_value(row,'vendor_relations') or []; rels=rels if isinstance(rels,list) else [rels]
                for rel in rels:
                    head=str(rel).split('·',1)[0].strip(); m=manufacturer_by_key.get(canonical(head))
                    if m:
                        evs=_field_evidence(row,'vendor_relations')
                        if evs: _merge_field_list(row,'westcon_overlap',m.get('name'),evs[0],.88)
    return stats


def enrich_private_accounts(data: dict[str, Any]) -> dict[str, int]:
    research=load('data/research.latest.json',{})
    rows={canonical(r.get('name')):r for r in data.get('clients_private',[]) if r.get('name')}
    manufacturers={canonical(r.get('name')):r.get('name') for r in data.get('manufacturers',[]) if r.get('name')}
    stats={'official_pages':0,'technology_fields':0,'hiring_fields':0,'vendor_fit_signals':0}
    for raw in research.get('evidence') or []:
        if raw.get('entityKind')!='client' or not raw.get('sourceEntity'): continue
        row=rows.get(canonical(raw.get('sourceEntity')));
        if not row: continue
        tier=norm(raw.get('sourceTier')); engine=norm(raw.get('engine'))
        if tier not in {'official company','official-company'} and 'official ecosystem sitemap' not in engine: continue
        ev=ev_obj(raw); dims=set(raw.get('profileDimensions') or []); stats['official_pages']+=1
        tech=[]
        for dim in ('capabilities','services'):
            tech.extend(_labels_from_taxonomy(raw,dim))
        for label in dict.fromkeys(tech):
            _merge_field_list(row,'technology_signals',label,ev,.84);stats['technology_fields']+=1
        if 'job_profiles' in dims:
            jobs=_labels_from_taxonomy(raw,'job_profiles')
            if not jobs: jobs=['Tecnología / IT · vacantes observadas']
            for label in jobs:
                _merge_field_list(row,'hiring_signals',label,ev,.72);stats['hiring_fields']+=1
        vendor=raw.get('vendor')
        if vendor and 'job_profiles' not in dims:
            m=manufacturers.get(canonical(vendor))
            if m:
                _merge_field_list(row,'westcon_fit',m,ev,.86);stats['vendor_fit_signals']+=1
        if tech or 'public_cases' in dims:
            title=str(raw.get('title') or '').strip()
            note=(title[:180] if title else 'Señal tecnológica observada en fuente corporativa oficial.')
            _merge_field_list(row,'opportunity_notes',note,ev,.78)
    return stats


def mark_direct_sales(data: dict[str, Any]) -> int:
    phrases=["venta directa","ventas directas","vende directamente","direct sales","sells direct","sell direct","direct to customer","direct-to-customer","buy direct"]
    count=0
    for row in data.get("manufacturers",[]):
        blob=" ".join(str(ev.get(k) or '') for ev in row.get('evidence') or [] for k in ('title','description','source'))
        blob=norm(blob)
        detected=any(norm(p) in blob for p in phrases)
        row['direct_sales']=bool(detected)
        if detected:
            row['direct_sales_label']='Venta directa detectada'
            row['direct_sales_evidence']=dedupe_evidence(row.get('evidence') or [],8)
            count+=1
    return count


def build() -> dict[str, Any]:
    data=copy.deepcopy(build_v39())
    data.setdefault('meta',{})['version']=VERSION
    data['meta']['generated_at']=datetime.now(timezone.utc).isoformat()
    data['meta']['principle']='Inteligencia descriptiva y trazable con clasificación positiva de mayoristas, cobertura estructural de grandes cuentas y relaciones fabricante↔integrador respaldadas por evidencia.'
    data['meta']['traceability']='Mayoristas requiere evidencia positiva explícita. Clientes públicos enlazan el anuncio exacto. Encaje Westcon solo admite fabricantes presentes en el portfolio activo. Relaciones de ecosistema conservan alcance geográfico.'
    data['source_catalog']=merge_source_catalog(); data['meta']['source_count']=len(data['source_catalog'])

    _ensure_schema(data,'distributors',[
        {'id':'validation_status','label':'Validación mayorista','help':'La entidad solo aparece si una fuente fiable la clasifica explícitamente como distribuidor/mayorista/VAD.','clarify':True},
        {'id':'distributor_type','label':'Tipo de mayorista','help':'Broadliner, VAD, especializado, volumen u otra tipología observable.','clarify':True},
        {'id':'market_position','label':'Posición mercado','help':'Ranking/posición cuando una fuente de canal publica una referencia explícita.','clarify':True},
    ])
    _ensure_schema(data,'clients_public',[
        {'id':'notice_id','label':'Expediente / anuncio','help':'Identificador exacto del anuncio público; Información abre el expediente concreto.','clarify':True},
        {'id':'source_portal','label':'Portal oficial','help':'Fuente oficial concreta del expediente; no una portada genérica.','clarify':True},
    ])
    _ensure_schema(data,'clients_private',[
        {'id':'index_universe','label':'Universo de cuenta','help':'Índice oficial utilizado para garantizar cobertura mínima completa: IBEX 35 o PSI.','clarify':True},
    ],prepend=False)

    data['meta']['portfolio_fit_cleanup']=sanitize_westcon_fit(data)
    data['meta']['distributor_validation']=validate_distributors(data)
    data['meta']['private_account_universe']=build_private_accounts(data)
    # Sanitise again after richer existing private rows were merged into the full universe.
    second=sanitize_westcon_fit(data)
    data['meta']['portfolio_fit_cleanup']['removed_nonportfolio_private'] += second['removed_nonportfolio_private']
    data['meta']['public_procurement']=build_public_procurement(data)
    data['meta']['integrator_graph']=expand_integrator_graph(data)
    data['meta']['entity_profile_enrichment']=enrich_entity_profiles(data)
    data['meta']['private_account_enrichment']=enrich_private_accounts(data)
    data['meta']['direct_sales_manufacturers']=mark_direct_sales(data)
    return data


def write_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    write('data/v313/intelligence.json',data)
    gaps=build_gaps(data)
    graph=data.get('meta',{}).get('integrator_graph',{}) or {}
    gaps['note']='v3.13 calcula los huecos sobre el dataset actual y prioriza perfiles de integrador/mayorista, ecosistema, grandes cuentas y contratación. No hereda el contador 559 de versiones anteriores.'
    gaps['v313_priority_manufacturers']=graph.get('manufacturers_below_3_integrators',[])
    write('data/v313/research_gaps.json',gaps)
    traceable_fields=sum(1 for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures') for row in data.get(section,[]) or [] for spec in (row.get('fields') or {}).values() if spec and spec.get('evidence'))
    result={
        'version':VERSION,'generated_at':data['meta']['generated_at'],'finished_at':data['meta']['generated_at'],'profile':'snapshot','status':'published',
        'manufacturers':len(data.get('manufacturers') or []),'distributors':len(data.get('distributors') or []),'integrators':len(data.get('integrators') or []),
        'clients':len(data.get('clients_public') or [])+len(data.get('clients_private') or []),'clients_public':len(data.get('clients_public') or []),'clients_private':len(data.get('clients_private') or []),
        'clients_private_es':data['meta']['private_account_universe'].get('ibex35',0),'clients_private_pt':data['meta']['private_account_universe'].get('psi',0),
        'trends':len(data.get('trends') or []),'architectures':len(data.get('architectures') or []),'source_count':len(data.get('source_catalog') or []),'traceable_fields':traceable_fields,
        'research_gaps':gaps.get('total_gaps',0),'high_priority_research_gaps':gaps.get('high_priority_gaps',0),
        'gap_by_section':gaps.get('by_section',{}),'gap_missing_by_field':gaps.get('missing_by_field',{}),
        'distributor_validation':data['meta'].get('distributor_validation'), 'portfolio_fit_cleanup':data['meta'].get('portfolio_fit_cleanup'),
        'public_procurement':data['meta'].get('public_procurement'),'integrator_graph':data['meta'].get('integrator_graph'),
        'research_policy':{'distributors':'positive-validation-first','public_procurement':'exact-link-only','private_accounts':'IBEX35+PSI-complete','ecosystem':'bidirectional-evidence-first'},
    }
    write('data/v313/last_run.json',result); return result


if __name__=='__main__':
    result=write_snapshot(build())
    print(json.dumps(result,ensure_ascii=False))
