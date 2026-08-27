from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

TOKEN_STOP = {
    "the","and","for","with","from","this","that","into","para","por","con","una","uno","del","las","los","que","como","en","de","la","el","y","a","se","su","sus","em","do","da","dos","das","com","uma","um","e","o","as","os",
    "spain","espana","españa","portugal","global","iberia"
}

EVENT_BASE = {
    "distribution_agreement": .94, "ma_acquisition": .94, "ma_rumor": .68, "procurement_award": .90, "procurement_notice": .78,
    "partnership": .84, "investment": .82, "customer_reference": .80, "market_expansion": .80,
    "channel_program": .78, "certification": .76, "managed_service": .80, "service_launch": .76,
    "product_release": .72, "capability_expansion": .74, "analyst_positioning": .74,
    "regulatory_change": .82, "security_incident": .78, "operational_incident": .62,
    "pricing_licensing": .72, "end_of_sale": .80, "financial_performance": .58,
    "leadership_change": .60, "hiring": .50, "award": .56, "strategy": .55,
    "technology_trend": .66, "known_exploited_vulnerability": .84, "security_vulnerability": .70, "unknown": .34,
}

EVENT_ACTION = {
    "distribution_agreement": "Revisar presión de canal, cobertura y exclusividad; preparar defensa o captura.",
    "ma_acquisition": "Evaluar cambio de poder de mercado, conflictos de portfolio y oportunidades de integración.",
    "ma_rumor": "Verificar con fuentes primarias antes de actuar; modelar escenarios solo como hipótesis hasta confirmar negociación o transacción.",
    "procurement_award": "Mapear comprador, adjudicatario, tecnologías y partners; extraer aprendizaje del contrato adjudicado y cuentas análogas.",
    "procurement_notice": "Priorizar la licitación tecnológica, identificar comprador, requisitos, fabricantes y partners con capacidad para concurrir.",
    "partnership": "Evaluar sinergias, desplazamientos y posibilidad de réplica multivendor.",
    "customer_reference": "Usar como prueba de demanda y buscar cuentas/verticales comparables en Iberia.",
    "certification": "Validar capacidad técnica real del partner y oportunidad de activar fabricantes Westcon.",
    "managed_service": "Evaluar attach de servicios recurrentes y diferenciación de mayorista/integrador.",
    "service_launch": "Analizar monetización, enablement y competencia con servicios de Westcon/partners.",
    "product_release": "Actualizar enablement, demos, campañas y compatibilidades de portfolio.",
    "analyst_positioning": "Contrastar posicionamiento y convertirlo en argumentario comercial verificable.",
    "security_incident": "Priorizar mitigación, servicios attach y comunicación técnica al canal.",
    "regulatory_change": "Traducir el cambio a obligación, demanda potencial y oferta comercial.",
    "known_exploited_vulnerability": "Priorizar advisories, exposición instalada, mitigación y servicios de hardening/managed security para partners afectados.",
    "security_vulnerability": "Correlacionar criticidad, explotación y base instalada antes de elevar una acción comercial o técnica.",
}

OTHER_REGIONS = {
    "costa rica","chile","argentina","brasil","brazil","mexico","méxico","colombia","peru","perú","uruguay","paraguay","ecuador","bolivia","panama","panamá","latinoamerica","latinoamérica","latin america","america latina","américa latina","caribbean","canada","canadá","united states","estados unidos","usa","india","japan","japón","australia","singapore","singapur"
}
EUROPE_WORDS = {"europe","europa","european","europea","europeu","europeia","eu"}
EMEA_WORDS = {"emea","middle east and africa","europa oriente medio africa"}
GLOBAL_WORDS = {"global","worldwide","mundial","world","international","internacional"}

PATTERNS: Sequence[Tuple[str, Sequence[str]]] = (
    ("distribution_agreement", (
        r"\b(distribution agreement|distribution deal|appointed .* distributor|selected .* distributor|global distributor|distribuidor(?:a)? (?:global|oficial)|acuerdo de distribuci[oó]n|acordo de distribui[cç][aã]o|ser[aá] distribuidor)\b",
    )),
    ("ma_rumor", (
        r"\b(in talks to acquire|talks? to acquire|considering (?:an )?acquisition|mulls? (?:an )?acquisition|explores? (?:an )?acquisition|reportedly .* (?:buy|acquire)|negocia(?:ndo)? (?:la )?compra|negocia(?:ndo)? (?:una )?adquisici[oó]n|estudia (?:la )?compra|explora (?:la )?compra|podr[ií]a comprar)\b",
    )),
    ("ma_acquisition", (
        r"\b(acquires|acquired|acquisition of|to acquire|merger with|merges with|adquiere|adquisici[oó]n de|compra de|compra a|fusi[oó]n con|aquisi[cç][aã]o de|adquire)\b",
    )),
    ("investment", (
        r"\b(invests? in|investment in|stake in|participaci[oó]n de|invierte en|investimento em|adquiere el \d+%|acquires? \d+% stake)\b",
    )),
    ("procurement_award", (
        r"\b(contract award|awarded contract|public tender|procurement|licitaci[oó]n|adjudicaci[oó]n|adjudica(?:do|da)|contrato p[uú]blico|concurso p[uú]blico|contrata[cç][aã]o p[uú]blica)\b",
    )),
    ("partnership", (
        r"\b(strategic partnership|partners? with|partnership with|strategic alliance|alliance with|alianza estrat[eé]gica|se al[ií]a con|acuerdo estrat[eé]gico|acordo estrat[eé]gico|parceria estrat[eé]gica|firman un acuerdo|assinam um acordo)\b",
    )),
    ("analyst_positioning", (
        r"\b(gartner|magic quadrant|forrester wave|forrester|idc marketscape|idc marketshare|omdia|canalys|leader in .* quadrant|l[ií]der en .* cuadrante)\b",
    )),
    ("customer_reference", (
        r"\b(chooses|selects|selected .* to|deploys|adopts|becomes .* customer|customer story|case study|se convierte .* clientes?|cliente(?:s)? de|elige a|selecciona a|implanta .* con|de la mano de|apuesta por .* con|escolhe|seleciona|implementa .* com|cliente da|cliente de)\b",
    )),
    ("certification", (
        r"\b(certified|certification|certificaci[oó]n|certifica[cç][aã]o|specialization|specialisation|especializaci[oó]n|especializa[cç][aã]o)\b",
    )),
    ("award", (
        r"\b(partner of the year|distributor of the year|distribuidor del ano|distribuidor del año|award(?:ed|s)?|winner|premio(?:s)?|pr[eé]mio(?:s)?|galard[oó]n|reconocimiento|reconhecida)\b",
    )),
    ("managed_service", (
        r"\b(managed service|managed services|mssp|soc as a service|security operations center|servicio gestionado|servicios gestionados|servi[cç]os geridos|oneSOC|white.?label soc)\b",
    )),
    ("service_launch", (
        r"\b(launches? .* service|new service|service offering|lanza .* servicio|nuevo servicio|lan[cç]a .* servi[cç]o|nova oferta de servi[cç]os)\b",
    )),
    ("end_of_sale", (
        r"\b(end of sale|end-of-sale|end of life|end-of-life|eol|retirement|discontinued|fin de venta|fin de vida|fim de vida|descontinua)\b",
    )),
    ("pricing_licensing", (
        r"\b(pricing|price increase|licensing|license model|subscription price|precios|subida de precios|licenciamiento|licenciamento|modelo de licencia)\b",
    )),
    ("operational_incident", (
        r"\b(outage|service disruption|interruption|interruptions|downtime|ca[ií]da del servicio|interrupci[oó]n(?:es)? del servicio|indisponibilidade)\b",
    )),
    ("security_incident", (
        r"\b(data breach|breach|ransomware|cyberattack|cyber attack|security incident|incidente de seguridad|ciberataque|violaci[oó]n de datos|incidente de ciberseguran[cç]a)\b",
    )),
    ("financial_performance", (
        r"\b(earnings|revenue|quarterly results|annual results|guidance|ebitda|eps|bpa|ingresos|resultados trimestrales|resultados anuales|facturaci[oó]n|receita|resultados do trimestre)\b",
    )),
    ("leadership_change", (
        r"\b(new ceo|new country manager|nuevo ceo|nuevo director general|nuevo country manager|nombra .* ceo|nombra .* director|nomeia .* ceo|novo diretor geral|nova diretora geral)\b",
    )),
    ("hiring", (
        r"\b(hiring|hires? \d+|jobs|vacancies|recruitment|contrata \d+|incorpora \d+|empleos|vacantes|recrutamento|vagas)\b",
    )),
    ("market_expansion", (
        r"\b(expands? into|opens? .* office|new office|enters? .* market|expansi[oó]n|entra en .* mercado|abre .* oficina|expans[aã]o|entra no mercado|abre escrit[oó]rio)\b",
    )),
    ("channel_program", (
        r"\b(partner program|channel program|partner programme|programa de partners|programa de canal|programa de parceiros|marketplace partner)\b",
    )),
    ("capability_expansion", (
        r"\b(new practice|new business unit|center of excellence|centre of excellence|reorganiza .* [aá]reas|nueva [aá]rea|unidad de negocio|centro de excelencia|nova [aá]rea|unidade de neg[oó]cio|deploys its .* (?:strategy|architecture|stack)|despliega su .* (?:apuesta|arquitectura|plataforma))\b",
    )),
    ("product_release", (
        r"\b(launches?|release[sd]?|unveils?|introduces?|launch|lanza(?:n|ra|rá)?|presenta(?:n|ra|rá)?|anuncia(?:n|ra|rá)?|lan[cç]a(?:m|ra|rá)?|apresenta(?:m|ra|rá)?)\b.*\b(platform|software|version|release|appliance|product|products|solution|solutions|soluci[oó]n(?:es)?|plataforma|versi[oó]n|produto|solu[cç][aã]o|pan-os|firewall|switch|router)\b",
    )),
    ("regulatory_change", (
        r"\b(regulation|directive|law|compliance requirement|reglamento|directiva|ley|normativa|regula[cç][aã]o|diretiva|lei|conformidade)\b",
    )),
)

NOISE_PATTERNS = (
    r"\b(recommendation de compra|recomendaci[oó]n de compra|buy recommendation|buy rating|price target|precio objetivo|target price)\b",
    r"\b(earnings to watch|reports .* tomorrow|estimaci[oó]n de resultados|earnings estimate)\b",
)


def _norm(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).casefold()


def _tokens(text: Any) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]{3,}", _norm(text)) if x not in TOKEN_STOP}


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        d = parsedate_to_datetime(str(value))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def freshness(value: Any) -> Tuple[str, float]:
    dt=_parse_date(value)
    if not dt: return "unknown", .52
    age=max(0.0,(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/86400)
    score=max(.08,min(1.0,2**(-age/240.0)))
    band="current" if age<=90 else ("recent_context" if age<=365 else "historical_context")
    return band,round(score,3)

def classify_event(record: Mapping[str, Any]) -> Tuple[str, float, str]:
    blob = " ".join(str(record.get(k) or "") for k in ("title","headline","summary","description")).strip()
    n = _norm(blob)
    # Structured official procurement evidence beats lexical semantics. Portuguese/Spanish
    # "aquisição/adquisición" describes what the authority is buying; it is not corporate M&A.
    if str(record.get("evidence_kind") or "") == "public_procurement" or str(record.get("dimension") or "") in {"procurement_notice","procurement_award"}:
        phase=str(record.get("procurement_phase") or "").lower()
        if phase=="award" or str(record.get("dimension") or "")=="procurement_award":
            return "procurement_award", .97, "structured_public_procurement_award"
        return "procurement_notice", .96, "structured_public_procurement_notice"
    for pat in NOISE_PATTERNS:
        if re.search(pat, n, re.I):
            return "financial_performance", .45, "market_noise"
    # Award phrases must beat distributor terms; procurement must contain public-contract context.
    for event_type, pats in PATTERNS:
        for pat in pats:
            if re.search(pat, n, re.I):
                if event_type == "ma_acquisition" and re.search(r"\b(compras|purchasing|procurement department)\b", n):
                    continue
                if event_type == "ma_acquisition" and re.search(r"\b(adquiere|acquires?|compra)\b.{0,25}\b\d{1,2}%", n):
                    return "investment", .84, "minority_stake"
                if event_type == "certification" and re.search(r"\b(students?|estudiantes?|alumnos?|formandos?)\b", n):
                    return "technology_trend", .48, "third_party_certification"
                return event_type, min(.96, EVENT_BASE.get(event_type,.6) + .03), "semantic_pattern"
    legacy = str(record.get("dimension") or record.get("classification") or "").lower()
    fallback = {
        "distribution":"distribution_agreement", "procurement":"procurement_notice", "procurement_notice":"procurement_notice", "procurement_award":"procurement_award", "customers":"customer_reference",
        "services":"service_launch", "certification":"certification", "awards":"award", "ma":"ma_acquisition",
        "hiring":"hiring", "competitive":"strategy", "security_incident":"security_incident", "known_exploited_vulnerability":"known_exploited_vulnerability", "security_vulnerability":"security_vulnerability", "financial_performance":"financial_performance", "market":"technology_trend"
    }.get(legacy, "unknown")
    return fallback, max(.38, EVENT_BASE.get(fallback,.4)-.10), "legacy_fallback"


def detect_scope(record: Mapping[str, Any]) -> Tuple[str, float]:
    blob = _norm(" ".join(str(record.get(k) or "") for k in ("title","summary","description","country","geography","market","region")))
    if re.search(r"\b(iberia|iberian|espana y portugal|spain and portugal|espanha e portugal)\b", blob): return "IBERIA", 1.0
    has_es = bool(re.search(r"\b(spain|espana|madrid|barcelona|valencia|sevilla|bilbao)\b", blob))
    has_pt = bool(re.search(r"\b(portugal|lisboa|lisbon|porto)\b", blob))
    if has_es and has_pt: return "IBERIA", 1.0
    if has_es: return "ES", 1.0
    if has_pt: return "PT", 1.0
    if any(x in blob for x in OTHER_REGIONS): return "OTHER_REGION", .20
    if any(re.search(rf"\b{re.escape(x)}\b", blob) for x in EMEA_WORDS): return "EMEA", .82
    if any(re.search(rf"\b{re.escape(x)}\b", blob) for x in EUROPE_WORDS): return "EUROPE", .86
    if any(re.search(rf"\b{re.escape(x)}\b", blob) for x in GLOBAL_WORDS): return "GLOBAL", .75
    country = str(record.get("country") or "").upper()
    if country in {"ES","PT","IBERIA"}: return country, 1.0
    if country == "GLOBAL": return "GLOBAL", .75
    return "UNKNOWN", .45


def extract_object(record: Mapping[str, Any], event_type: str) -> str:
    title = str(record.get("title") or record.get("headline") or "")
    entity = str(record.get("entity_name") or "").strip()
    # Structured direct evidence always beats title heuristics.
    buyer=str(record.get("buyer_name") or "").strip(); winner=str(record.get("winner_name") or "").strip()
    if event_type in {"procurement_award","procurement_notice"}:
        # If the seeded entity is the winner, connect it to the buyer. For a market-level
        # procurement event preserve the concrete winner when one exists.
        if winner and winner.casefold()!=entity.casefold(): return winner[:100]
        if buyer and buyer.casefold()!=entity.casefold(): return buyer[:100]
    if event_type in {"known_exploited_vulnerability","security_vulnerability"}:
        product=str(record.get("product") or "").strip(); cve=str(record.get("cve") or "").strip()
        value=" · ".join(x for x in [product,cve] if x)
        if value:return value[:100]
    for key in ("counterparty","partner_name","customer_name","target_name","object_entity"):
        v=str(record.get(key) or "").strip()
        if v and v.casefold()!=entity.casefold():return v[:100]
    patterns = {
        "ma_acquisition": [r"(?:acquires|adquiere|compra|adquire)\s+(?:a\s+|el\s+\d+%\s+de\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w&.ÁÉÍÓÚÑÇãõáéíóú\- ]{2,60})"],
        "ma_rumor": [r"(?:negocia(?:ndo)? (?:la )?compra de|in talks to acquire|considering (?:an )?acquisition of)\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w&.ÁÉÍÓÚÑÇãõáéíóú\- ]{2,60})"],
        "investment": [r"(?:invierte en|invests? in|adquiere el \d+% de|acquires? \d+% stake in)\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w&.ÁÉÍÓÚÑÇãõáéíóú\- ]{2,60})"],
        "partnership": [r"(?:with|con|com)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w&.ÁÉÍÓÚÑÇãõáéíóú\- ]{2,60})", r"^([A-Z0-9][\w&.\- ]{2,50}),?\s+(?:SAP|Microsoft|AWS|Google Cloud|Cisco).{0,40}(?:acuerdo|partnership|alianza)"],
        "distribution_agreement": [r"^([A-Z0-9][\w&.\- ]{2,50}),?\s+(?:seleccionada|selected|nombrada|appointed|ser[aá]|sera).{0,40}distrib", r"(?:distribuidor(?:a)? (?:global|oficial) de|distributor (?:for|of))\s+([A-Z0-9][\w&.\- ]{2,50})"],
        "customer_reference": [
            r"^([A-Z0-9][\w&.\- ]{2,60})\s+(?:se convierte|chooses|selects|elige|selecciona|apuesta)",
            r"^([A-Z0-9][\w&.\- ]{2,60})\s+(?:aplica|innova|inova|implementa|transforma).{0,120}(?:de la mano de|con soluciones de|com solu[cç][oõ]es de)"
        ],
        "award": [r"(?:de|of)\s+([A-Z][\w&.\- ]{2,50})\s+(?:como|as|Partner|Distributor)", r"^([A-Z][\w&.\- ]{2,50})\s+(?:reconoce|recognizes|premia|awards)"],
    }
    for pat in patterns.get(event_type, []):
        m = re.search(pat, title, re.I)
        if m:
            value = re.sub(r"\s+-\s+.*$", "", m.group(1)).strip(" ,.:;'")
            if value and value.casefold() != entity.casefold():
                return value[:100]
    return ""

def stable_event_id(entity: str, event_type: str, obj: str, title: str) -> str:
    core = f"{_norm(entity)}|{event_type}|{_norm(obj)}|{' '.join(sorted(_tokens(title))[:12])}"
    return hashlib.sha1(core.encode("utf-8")).hexdigest()[:16]


def event_materiality(event_type: str, scope_score: float, source_authority: float, westcon_relevance: float, corroboration: int, freshness_score: float=.6, noise_reason: str = "", strategic_fit: float=.5) -> float:
    base = EVENT_BASE.get(event_type, .42)
    corr = min(1.0, .45 + .16 * max(0, corroboration-1))
    value = .28*base + .12*scope_score + .10*source_authority + .15*westcon_relevance + .08*corr + .12*freshness_score + .15*strategic_fit
    if noise_reason == "market_noise": value -= .24
    return round(max(0.0, min(1.0, value)), 3)


def confidence_score(source_authority: float, classification_confidence: float, scope_score: float, corroboration: int, direct: bool, contradiction: float = 0.0) -> float:
    corr = min(1.0, .44 + .18 * max(0, corroboration-1))
    v = .27*source_authority + .23*classification_confidence + .16*scope_score + .18*corr + .16*(.94 if direct else .62) - .18*contradiction
    return round(max(0.0, min(1.0, v)),3)


def westcon_relevance(record: Mapping[str, Any], scope: str, event_type: str, westcon_vendors: set[str], entity_types: Mapping[str,str]) -> float:
    entity = str(record.get("entity_name") or "").casefold()
    et = str(record.get("entity_type") or entity_types.get(entity) or "")
    rel = .30 if et=="market" else .54
    if entity in westcon_vendors: rel += .24
    if et in {"distributor","integrator"}: rel += .11
    if scope in {"ES","PT","IBERIA"}: rel += .17
    elif scope in {"EUROPE","EMEA"}: rel += .07
    elif scope == "OTHER_REGION": rel -= .46
    procurement_fit=float(record.get("procurement_fit_score") or 0)
    if event_type in {"procurement_award","procurement_notice"}:
        # Public-sector demand is only strongly relevant when it maps to Westcon's strategic domains.
        rel += .16*procurement_fit
        if procurement_fit < .5: rel -= .10
    if event_type in {"distribution_agreement","ma_acquisition","partnership","managed_service","market_expansion","regulatory_change"}: rel += .08
    if event_type=="known_exploited_vulnerability":
        rel += .06 if entity in westcon_vendors else -.04
    if event_type in {"financial_performance","hiring","award","leadership_change"}: rel -= .06
    return round(max(.05,min(1.0,rel)),3)


TECH_PATTERNS = {
    "AI": r"\b(ai|artificial intelligence|inteligencia artificial|ia|agentic|agentica|ag[eê]ntica|machine learning|genai|generative ai)\b",
    "Cybersecurity": r"\b(cyber|cybersecurity|ciberseguridad|ciberseguranca|security|seguridad|zero trust|soc|xdr|edr|siem|ransomware)\b",
    "SASE/SSE": r"\b(sase|sse|secure service edge|security service edge)\b",
    "Networking": r"\b(network|networking|red(?:es)?|switch|router|wifi|wi-fi|sd-wan|ethernet|5g|ran)\b",
    "Cloud": r"\b(cloud|nube|aws|azure|gcp|saas|paas|iaas|sovereign cloud|nuvem)\b",
    "Data Center": r"\b(data ?center|datacenter|centro de datos|centro de dados|server|servidor|storage)\b",
    "Observability": r"\b(observability|observabilidad|monitoring|telemetry|apm|network visibility)\b",
    "Automation": r"\b(automation|automatizacion|automatizacao|orchestration|orquestacion|robotic process|rpa)\b",
    "Identity": r"\b(identity|identidad|iam|pam|mfa|authentication|autenticacion)\b",
    "IT Services": r"\b(informatica|informatico|information technology|tecnologia de la informacion|tic|ict|software|software development|desarrollo de software|programacion de software|desarrollo aplicacional|aplicacional|servicios? de tecnologia|servicos? de tecnologia|soporte informatico|it support)\b",
}

def technology_domains(record: Mapping[str,Any]) -> List[str]:
    blob=_norm(" ".join(str(record.get(k) or "") for k in ("title","summary","description")))
    return [name for name,pat in TECH_PATTERNS.items() if re.search(pat,blob,re.I)]

def _effective_procurement_fit(record: Mapping[str,Any], techs: Sequence[str]) -> float:
    try:
        explicit=float(record.get("procurement_fit_score") or 0)
        if explicit>0:return explicit
    except Exception: pass
    strategic={"AI","Cybersecurity","SASE/SSE","Networking","Cloud","Data Center","Observability","Automation","Identity"}
    if strategic.intersection(set(techs)):return .82
    if "IT Services" in set(techs):return .42
    return .20 if bool(record.get("technology_procurement")) else 0.0

def strategic_fit_score(record: Mapping[str,Any], event_type:str, techs: Sequence[str], relevance:float, scope:str, westcon_vendors:set[str]) -> float:
    entity=str(record.get("entity_name") or "").casefold()
    fit=.42
    if entity in westcon_vendors: fit+=.18
    if scope in {"ES","PT","IBERIA"}: fit+=.12
    elif scope in {"EUROPE","EMEA"}: fit+=.06
    elif scope=="OTHER_REGION": fit-=.20
    strategic_domains={"AI","Cybersecurity","SASE/SSE","Networking","Cloud","Data Center","Observability","Automation","Identity"}
    if strategic_domains.intersection(set(techs)): fit+=.16
    elif techs==["IT Services"] or set(techs)=={"IT Services"}: fit-=.10
    if event_type in {"distribution_agreement","managed_service","market_expansion","ma_acquisition","partnership","regulatory_change"}: fit+=.10
    if event_type in {"financial_performance","award","hiring","leadership_change"}: fit-=.12
    if event_type in {"procurement_notice","procurement_award"}:
        pf=float(record.get("procurement_fit_score") or 0)
        fit=.22+.55*pf+(.10 if scope in {"ES","PT","IBERIA"} else 0)
    if event_type=="known_exploited_vulnerability":
        fit=.48+(.20 if entity in westcon_vendors else 0)
        try:
            epss=float(record.get("epss") or 0); fit+=min(.18,epss*.20)
        except Exception: pass
    return round(max(.05,min(1.0,fit)),3)

def evidence_grade(source_authority:float, direct:bool, source_category:str) -> str:
    if direct and source_authority>=.94:return "A"
    if source_category in {"official","regulatory","vendor","distributor","integrator"} and source_authority>=.85:return "A"
    if source_authority>=.78:return "B"
    if source_authority>=.62:return "C"
    return "D"

def build_candidate_event(record: Mapping[str, Any], *, source_authority: float, westcon_vendors: set[str], entity_types: Mapping[str,str], direct: bool=False) -> Dict[str, Any]:
    event_type, cls_conf, reason = classify_event(record)
    scope, scope_score = detect_scope(record)
    if event_type=="analyst_positioning" and str(record.get("source_category") or "") not in {"analyst","official"}:
        cls_conf=max(.45,cls_conf-.12); reason+="+secondary_analyst_claim"
    obj = extract_object(record,event_type)
    entity = str(record.get("entity_name") or record.get("vendor") or record.get("name") or "Market").strip()
    techs = technology_domains(record)
    effective_record=dict(record)
    if event_type in {"procurement_notice","procurement_award"}: effective_record["procurement_fit_score"]=_effective_procurement_fit(record,techs)
    relevance = westcon_relevance(effective_record, scope, event_type, westcon_vendors, entity_types)
    strategic_fit = strategic_fit_score(effective_record,event_type,techs,relevance,scope,westcon_vendors)
    source_category=str(record.get("source_category") or "")
    grade=evidence_grade(source_authority,bool(direct),source_category)
    freshness_band,freshness_score=freshness(record.get("published_at") or record.get("date") or record.get("observed_at"))
    is_westcon_vendor=entity.casefold() in westcon_vendors
    object_is_westcon_vendor=bool(obj and obj.casefold() in westcon_vendors)
    return {
        "event_id": stable_event_id(entity,event_type,obj,str(record.get("title") or "")),
        "event_type": event_type,
        "entity_name": entity,
        "entity_type": str(record.get("entity_type") or entity_types.get(entity.casefold()) or "market"),
        "object_entity": obj,
        "object_entity_type": str(entity_types.get(obj.casefold()) or "") if obj else "",
        "technology_domains": techs,
        "technologies": techs,
        "title": str(record.get("title") or record.get("headline") or "").strip(),
        "summary": str(record.get("summary") or record.get("description") or "").strip()[:1200],
        "published_at": record.get("published_at") or record.get("date"),
        "observed_at": record.get("observed_at") or datetime.now(timezone.utc).isoformat(),
        "market_scope": scope,
        "scope_score": scope_score,
        "freshness_band": freshness_band,
        "freshness_score": freshness_score,
        "source": str(record.get("source") or record.get("source_name") or ""),
        "source_id": str(record.get("source_id") or ""),
        "source_category": source_category,
        "source_authority": round(source_authority,3),
        "evidence_grade": grade,
        "strategic_fit": strategic_fit,
        "url": str(record.get("url") or ""),
        "classification_confidence": round(cls_conf,3),
        "classification_reason": reason,
        "westcon_relevance": relevance,
        "subject_is_westcon_vendor": is_westcon_vendor,
        "object_is_westcon_vendor": object_is_westcon_vendor,
        "direct_evidence": bool(direct),
        "raw_dimension": record.get("dimension"),
        "evidence_kind": record.get("evidence_kind"),
        "procurement_phase": record.get("procurement_phase"),
        "technology_procurement": bool(record.get("technology_procurement")),
        "procurement_fit_score": float(effective_record.get("procurement_fit_score") or 0),
        "epss": record.get("epss"),
        "buyer_name": record.get("buyer_name"),
        "winner_name": record.get("winner_name"),
        "cpv": record.get("cpv"),
        "notice_type": record.get("notice_type"),
        "external_id": record.get("external_id"),
    }


def _event_tokens(e: Mapping[str,Any]) -> set[str]:
    return _tokens(" ".join([str(e.get("title") or ""),str(e.get("object_entity") or ""),str(e.get("entity_name") or "")]))


def _date_bucket(e: Mapping[str,Any]) -> int:
    dt = _parse_date(e.get("published_at"))
    return int(dt.timestamp()//(86400*14)) if dt else 0


def cluster_events(events: Iterable[Mapping[str,Any]]) -> List[Dict[str,Any]]:
    buckets: Dict[Tuple[str,str], List[Dict[str,Any]]] = defaultdict(list)
    for raw in events:
        e=dict(raw)
        key=(str(e.get("entity_name") or "").casefold(),str(e.get("event_type") or "unknown"))
        buckets[key].append(e)
    merged=[]
    for key, rows in buckets.items():
        clusters: List[List[Dict[str,Any]]] = []
        for e in sorted(rows,key=lambda x:str(x.get("published_at") or "")):
            et=_event_tokens(e); eb=_date_bucket(e); placed=False
            for c in clusters:
                lead=c[0]; lt=_event_tokens(lead); lb=_date_bucket(lead)
                sim=len(et&lt)/max(1,len(et|lt))
                same_obj=bool(e.get("object_entity") and lead.get("object_entity") and _norm(e.get("object_entity"))==_norm(lead.get("object_entity")))
                if abs(eb-lb)<=1 and (sim>=.42 or same_obj or (sim>=.30 and len(et&lt)>=3)):
                    c.append(e); placed=True; break
            if not placed: clusters.append([e])
        for c in clusters:
            c.sort(key=lambda x:(float(x.get("source_authority") or 0),float(x.get("classification_confidence") or 0)),reverse=True)
            lead=dict(c[0]); sources=[]; urls=[]
            for r in c:
                if r.get("source") and r.get("source") not in sources:sources.append(r.get("source"))
                if r.get("url") and r.get("url") not in urls:urls.append(r.get("url"))
            lead["corroboration_count"]=len(sources)
            lead["corroborating_sources"]=sources[:12]
            lead["corroborating_urls"]=urls[:12]
            lead["source_diversity"]=len({str(r.get("source_category") or r.get("source_id") or r.get("source")) for r in c})
            lead["materiality"]=event_materiality(str(lead.get("event_type")),float(lead.get("scope_score") or .45),float(lead.get("source_authority") or .58),float(lead.get("westcon_relevance") or .5),len(sources),float(lead.get("freshness_score") or .52),str(lead.get("classification_reason") or ""),float(lead.get("strategic_fit") or .5))
            if str(lead.get("entity_type") or "")=="market":
                pf=float(lead.get("procurement_fit_score") or 0)
                factor=(.96 if pf>=.75 else (.82 if pf>=.5 else .66)) if bool(lead.get("technology_procurement")) else .72
                lead["materiality"]=round(float(lead["materiality"])*factor,3)
            lead["confidence"]=confidence_score(float(lead.get("source_authority") or .58),float(lead.get("classification_confidence") or .5),float(lead.get("scope_score") or .45),len(sources),bool(lead.get("direct_evidence")))
            lead["event_id"]=stable_event_id(str(lead.get("entity_name")),str(lead.get("event_type")),str(lead.get("object_entity")),str(lead.get("title")))
            merged.append(lead)
    merged.sort(key=lambda e:(float(e.get("materiality") or 0),float(e.get("confidence") or 0),str(e.get("published_at") or "")),reverse=True)
    return merged


def decision_hint(event: Mapping[str,Any]) -> str:
    return EVENT_ACTION.get(str(event.get("event_type")),"Vigilar, corroborar y elevar solo si cambia la materialidad o la proximidad a Iberia.")
