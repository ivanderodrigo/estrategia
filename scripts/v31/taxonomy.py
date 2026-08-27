from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, Mapping

PROCUREMENT_ANCHORS = {
    "tender", "tenders", "procurement", "contract notice", "award notice",
    "contract award", "framework agreement", "framework contract",
    "licitacion", "licitación", "adjudicacion", "adjudicación", "adjudicatario",
    "contratacion publica", "contratación pública", "expediente", "pliego",
    "ted.europa.eu", "contrataciondelsectorpublico", "base.gov.pt", "portal base",
    "entidade adjudicante", "procedimento", "concurso publico", "concurso público",
    "cpv", "contracting authority", "notice id",
}

NON_PROCUREMENT_AWARD_ANCHORS = {
    "partner of the year", "partner award", "customer award", "customer awards",
    "industry award", "industry awards", "security award", "innovation award",
    "excellence award", "award winner", "award-winning", "awards program",
    "awards programme", "recognition", "recognized", "recognised", "winner",
    "finalist", "gold award", "silver award", "bronze award", "readers' choice",
    "customers' choice", "customer choice", "best of", "prize", "premio", "premios",
    "galardon", "galardón", "reconocimiento", "vencedor", "prémio", "premio de",
    "distributor of the year", "distribuidor del año", "distribuidor do ano",
    "partner del año", "partner do ano", "socio del año", "parceiro do ano",
}

TAXONOMY = (
    "procurement_award",
    "customer_award",
    "vendor_award",
    "partner_award",
    "industry_award",
    "owned_awards_program",
    "customer_reference",
    "contract",
    "tender",
    "certification",
    "partnership",
    "distribution_agreement",
    "ma_activity",
    "service_launch",
    "product_release",
    "capability_change",
    "leadership_change",
    "hiring_signal",
    "strategy_growth",
    "analyst_signal",
    "market_signal",
    "other_signal",
    "pending_classification",
)


def _norm(value: Any) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _blob(record: Mapping[str, Any]) -> str:
    keys = (
        "title", "headline", "summary", "description", "text", "snippet", "source",
        "source_name", "url", "category", "classification", "type", "evidence_type",
        "buyer", "authority", "contracting_authority", "notice_type", "cpv", "award_name",
    )
    parts = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(x) for x in value)
        elif isinstance(value, dict):
            parts.extend(str(x) for x in value.values())
        elif value is not None:
            parts.append(str(value))
    return _norm(" | ".join(parts))


def _title(record: Mapping[str, Any]) -> str:
    return _norm(record.get("title") or record.get("headline") or "")


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(_norm(p) in text for p in phrases)


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(_norm(word))}(?!\w)", text) is not None


def procurement_anchor_score(record: Mapping[str, Any]) -> float:
    text = _blob(record)
    score = 0.0
    for phrase in PROCUREMENT_ANCHORS:
        if _norm(phrase) in text:
            score += 0.22
    for key in ("buyer", "contracting_authority", "authority", "notice_id", "cpv", "contract_value", "tender_id"):
        if record.get(key):
            score += 0.18
    url = _norm(record.get("url"))
    if any(domain in url for domain in ("ted.europa.eu", "contrataciondelsectorpublico", "base.gov.pt")):
        score += 0.35
    return min(score, 1.0)


def award_false_positive_score(record: Mapping[str, Any]) -> float:
    text = _blob(record)
    score = 0.0
    for phrase in NON_PROCUREMENT_AWARD_ANCHORS:
        if _norm(phrase) in text:
            score += 0.28
    if any(_norm(p) in text for p in ("distributor of the year", "distribuidor del año", "distribuidor do ano", "partner del año", "partner do ano", "partner of the year")):
        score += 0.38
    if re.search(r"\bawards?\b", text) and procurement_anchor_score(record) < 0.35:
        score += 0.34
    return min(score, 1.0)


def _is_ma(text: str) -> bool:
    strong = (
        "acquisition", "acquires", "acquired", "merger", "merges", "takeover", "buyout",
        "adquisicion", "adquisición", "adquiere", "adquirio", "adquirió", "fusion", "fusión", "fusao", "fusão",
        "acuerda la compra de", "acorda a compra de", "compra de la compania", "compra de la compañía",
        "venta de la compania", "venta de la compañía", "sale of the company",
    )
    if any(k in text for k in strong):
        return True
    # Spanish/Portuguese corporate verb, deliberately excluding comprar/compras.
    if re.search(r"\b(compra|adquire|adquiriu|comprou)\s+[a-z0-9]", text):
        return True
    return False


def _is_leadership(text: str) -> bool:
    phrases = (
        "nuevo ceo", "novo ceo", "new ceo", "nuevo director general", "novo diretor geral",
        "nuevo director", "nueva directora", "novo diretor", "nova diretora", "nuevo head", "novo head", "new head",
        "nuevo cmo", "nova cmo", "new cmo", "nuevo cto", "novo cto", "new cto", "nuevo cio", "novo cio", "new cio",
        "appointed ceo", "appointed cmo", "appointed cto", "appointed cio", "appointed director",
        "nombra a", "nomeia", "será el nuevo ceo", "sera el nuevo ceo", "será o novo ceo", "sera o novo ceo",
        "al frente del area", "al frente del área", "à frente da área", "a frente da area", "nuevo comando", "novo comando",
    )
    return any(p in text for p in phrases)


def _is_hiring(text: str) -> bool:
    # Hiring intentionally avoids generic contratación/contrata because it causes
    # false positives such as "contratación de préstamos".
    phrases = (
        "hiring", "vacancy", "vacancies", "job opening", "job openings", "careers", "ofertas de empleo",
        "ofertas de trabalho", "puestos vacantes", "vagas abertas", "contrata a ", "contrata nuevo", "contrata nova",
        "incorpora a ", "incorpora nuevo", "incorpora nova", "joins the company", "se incorpora a ",
    )
    return any(p in text for p in phrases)


def _is_certification(text: str) -> bool:
    phrases = (
        "certified", "certification", "certificacion", "certificación", "certificacao", "certificação",
        "accreditation", "acreditacion", "acreditación", "acreditacao", "acreditação",
        "gold partner", "platinum partner", "premier partner", "elite partner", "partner level",
        "specialization badge", "specialisation badge", "competency badge", "certified partner",
    )
    return any(p in text for p in phrases)


def _is_partnership(text: str) -> bool:
    phrases = (
        "partnership", "strategic alliance", "alianza estrategica", "alianza estratégica", "parceria estrategica", "parceria estratégica",
        "socio exclusivo", "parceiro exclusivo", "exclusive partner", "technology partner", "partner ecosystem",
        "acuerdo estrategico", "acuerdo estratégico", "acordo estrategico", "acordo estratégico",
    )
    return any(p in text for p in phrases)


def _is_distribution(text: str) -> bool:
    phrases = (
        "distribution agreement", "acuerdo de distribucion", "acuerdo de distribución", "acordo de distribuicao", "acordo de distribuição",
        "selected as distributor", "seleccionado como distribuidor", "seleccionada como distribuidor", "nombrado distribuidor",
        "nomeado distribuidor", "becomes distributor", "se convierte en distribuidor", "torna-se distribuidor",
        "distribuidor global", "global distributor", "distributor agreement",
    )
    return any(p in text for p in phrases)


def _is_strategy_growth(text: str) -> bool:
    phrases = (
        "plan estrategico", "plan estratégico", "strategic plan", "plano estrategico", "plano estratégico",
        "objetivo de ingresos", "revenue target", "objetivo de faturacao", "objetivo de faturação",
        "alcanzar los", "atingir os", "crecer hasta", "grow to", "growth target",
        "reestructura", "se reestructura", "reorganiza", "reorganización", "reorganizacao", "reorganização",
        "market positioning", "posicionamiento", "posicionamento",
    )
    return any(p in text for p in phrases)


def _is_capability_change(text: str) -> bool:
    phrases = (
        "areas de especializacion", "áreas de especialización", "areas de especializacao", "áreas de especialização",
        "se estructura en torno", "estrutura-se em torno", "new practice", "nueva practica", "nueva práctica",
        "nova pratica", "nova prática", "new business unit", "nueva unidad", "nova unidade",
    )
    return any(p in text for p in phrases)


@dataclass(frozen=True)
class ClassificationResult:
    classification: str
    confidence: float
    reason: str
    procurement_anchor_score: float
    award_false_positive_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_record(record: Mapping[str, Any]) -> ClassificationResult:
    text = _blob(record)
    title = _title(record)
    procurement_score = procurement_anchor_score(record)
    award_fp = award_false_positive_score(record)

    # HARD GUARD: award language can never become procurement by itself.
    if award_fp >= 0.55 and procurement_score < 0.55:
        if "distributor of the year" in text or "distribuidor del ano" in text or "distribuidor do ano" in text:
            label = "partner_award"
        elif "partner" in text or "socio" in text or "parceiro" in text:
            label = "partner_award"
        elif "customer" in text or "cliente" in text:
            label = "customer_award"
        elif "vendor" in text or "fabricante" in text:
            label = "vendor_award"
        else:
            label = "industry_award"
        return ClassificationResult(label, max(0.78, award_fp), "award-context-without-procurement-anchors", procurement_score, award_fp)

    if procurement_score >= 0.62:
        if any(k in text for k in ("award notice", "contract award", "adjudicacion", "adjudicación", "adjudicatario")):
            return ClassificationResult("procurement_award", max(0.72, procurement_score), "verified-procurement-award-anchors", procurement_score, award_fp)
        if any(k in text for k in ("tender", "licitacion", "licitación", "concurso publico", "concurso público", "pliego")):
            return ClassificationResult("tender", max(0.72, procurement_score), "verified-tender-anchors", procurement_score, award_fp)
        return ClassificationResult("contract", max(0.68, procurement_score), "procurement-contract-context", procurement_score, award_fp)

    # Strong event classes first. All are based primarily on title wording to avoid URL/source noise.
    if _is_ma(title):
        return ClassificationResult("ma_activity", 0.82, "ma-language", procurement_score, award_fp)
    if _is_leadership(title):
        return ClassificationResult("leadership_change", 0.80, "leadership-language", procurement_score, award_fp)
    if _is_hiring(title):
        return ClassificationResult("hiring_signal", 0.70, "hiring-language", procurement_score, award_fp)
    if _is_certification(title):
        return ClassificationResult("certification", 0.80, "certification-language", procurement_score, award_fp)
    if _is_distribution(title):
        return ClassificationResult("distribution_agreement", 0.82, "distribution-agreement-language", procurement_score, award_fp)
    if _is_partnership(title):
        return ClassificationResult("partnership", 0.77, "partnership-language", procurement_score, award_fp)
    if _is_capability_change(title):
        return ClassificationResult("capability_change", 0.73, "capability-structure-language", procurement_score, award_fp)
    if _is_strategy_growth(title):
        return ClassificationResult("strategy_growth", 0.72, "strategy-growth-language", procurement_score, award_fp)

    if any(k in title for k in ("informe", "report", "barometro", "barómetro", "market share", "cuota de mercado", "quota de mercado")):
        return ClassificationResult("market_signal", 0.66, "market-information-language", procurement_score, award_fp)

    # Executive interviews/quoted positioning are useful competitive-intelligence signals,
    # but are not M&A, hiring or distribution events.
    if any(role in title for role in ("director general", "ceo", "country manager", "vicepresidente", "vice president", "managing director")) and any(q in str(record.get("title") or "") for q in ("«", "»", "“", "”", '"', ":")):
        return ClassificationResult("market_signal", 0.64, "executive-market-positioning", procurement_score, award_fp)

    raw_title = str(record.get("title") or "")
    if any(q in raw_title for q in ("«", "»", "“", "”", '"')) and any(k in title for k in ("mercado", "market", "canal", "channel", "distribuidor", "distribution", "clientes", "customers", "negocio", "business", "tecnologico", "tecnológico", "technology", "financiero", "financial")):
        return ClassificationResult("market_signal", 0.62, "quoted-market-commentary", procurement_score, award_fp)

    if any(k in title for k in ("case study", "customer story", "success story", "caso de exito", "caso de éxito", "caso de sucesso", "cliente")):
        return ClassificationResult("customer_reference", 0.72, "customer-reference-language", procurement_score, award_fp)

    # Common customer-reference verbs where the customer is named in the headline.
    if any(k in title for k in ("de la mano de", "com solucoes da", "com soluções da", "con soluciones de", "aposta em", "adopta", "adopts", "implementa", "deploys", "despliega", "en colaboración con", "en colaboracion con", "em colaboração com", "em colaboracao com")):
        return ClassificationResult("customer_reference", 0.70, "customer-reference-verb", procurement_score, award_fp)

    if any(k in title for k in ("managed service", "managed services", "servicios gestionados", "serviços geridos", "professional services", "servicios profesionales", "serviços profissionais", "onesoc", "soc as a service", "noc as a service")):
        return ClassificationResult("service_launch", 0.78, "service-language", procurement_score, award_fp)

    if any(k in title for k in ("launches", "launch", "released", "release", "lanzamiento", "lanza", "lança", "lanca", "presenta nueva", "apresenta nova", "nuevo servicio", "novo servico", "novo serviço")):
        return ClassificationResult("product_release", 0.66, "product-release-language", procurement_score, award_fp)

    if any(k in text for k in ("gartner", "forrester", "idc", "omdia", "canalys", "dell'oro", "synergy research", "kuppingercole", "isg", "everest group", "gigaom")):
        return ClassificationResult("analyst_signal", 0.72, "analyst-source-language", procurement_score, award_fp)

    previous = _norm(record.get("classification") or record.get("category") or record.get("type"))
    if "procurement" in previous or "adjudic" in previous:
        return ClassificationResult("pending_classification", 0.41, "legacy-procurement-label-without-sufficient-anchors", procurement_score, award_fp)

    return ClassificationResult("other_signal", 0.50, "generic-public-signal", procurement_score, award_fp)


def repair_record(record: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    result = classify_record(record)
    current = _norm(record.get("classification") or record.get("evidence_type") or record.get("category"))
    changed = False
    if current != _norm(result.classification):
        unsafe_proc = ("procurement" in current or "adjudic" in current) and result.classification != "procurement_award"
        if result.confidence >= 0.68 or unsafe_proc:
            record["classification"] = result.classification
            changed = True
    record["classification_confidence"] = round(result.confidence, 3)
    record["classification_reason"] = result.reason
    record["procurement_anchor_score"] = round(result.procurement_anchor_score, 3)
    return record, changed
