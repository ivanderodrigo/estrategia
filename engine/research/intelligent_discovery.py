"""Evidence-preserving, sector-aware intelligence queries for Westcon Iberia.

These queries are DISCOVERY leads, not facts. Competing in the same segment does
not establish a competitive relationship. The existing extraction/provenance
gates must corroborate a named vendor before populating any field.
"""
from __future__ import annotations
from typing import Any

HIGH_VALUE_FIELDS = {
    "competitors": ("competitors alternative vendors", "competidores alternativas fabricantes", "concorrentes fabricantes"),
    "integrators": ("certified partners systems integrators", "integradores partners certificados", "parceiros integradores"),
    "distributors": ("authorized distributors channel", "mayoristas distribución", "distribuidores parceiros"),
    "capabilities": ("product technical datasheet architecture", "soluciones tecnología documentación técnica", "soluções tecnologia"),
    "products_platforms": ("products platforms portfolio", "plataformas productos soluciones", "produtos plataformas"),
    "use_cases": ("use cases customer story", "casos de uso caso de éxito", "casos de uso sucesso"),
    "services": ("professional services managed services", "servicios profesionales gestionados", "serviços geridos"),
    "recent_signals": ("latest product announcements press release", "novedades lanzamiento nota de prensa", "notícias lançamento"),
    "partner_program": ("channel partner program", "programa de partners", "programa de parceiros"),
    "certifications": ("technical certifications partner specializations", "certificaciones especializaciones", "certificações especializações"),
}
SOURCE_VARIANTS = (
    "comparative review independent analyst",
    "competitor comparison alternatives vendor",
    "market landscape networking cybersecurity cloud",
)


def _texts(field: Any, limit: int = 5) -> list[str]:
    if not isinstance(field, dict):
        return []
    value = field.get("value")
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split()).strip()
        if 3 <= len(text) <= 72 and text.casefold() not in {"unknown", "por investigar", "sin dato"}:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _topics(row: dict[str, Any]) -> list[str]:
    fields = row.get("fields") or {}
    topics: list[str] = []
    for field in ("domain", "subcategories", "capabilities", "products_platforms", "known_architectures", "use_cases"):
        topics.extend(_texts(fields.get(field), limit=3 if field in {"domain", "subcategories"} else 2))
    # Keep short category/product descriptions only, not sentence-length claims.
    topics = [value for value in topics if len(value.split()) <= 8]
    seen: set[str] = set()
    output: list[str] = []
    for topic in topics:
        key = topic.casefold()
        if key not in seen and key != str(row.get("name") or "").casefold():
            seen.add(key)
            output.append(topic)
    return output[:12]


def intelligent_discovery_queries(
    row: dict[str, Any],
    target_fields: list[str],
    *,
    section: str = "manufacturers",
    rotation: int = 0,
    limit: int = 8,
) -> list[str]:
    """Generate context-aware, multilingual, cross-field discovery instructions.

    Seeded from the entity's existing technology taxonomy and historical leads.
    Contextual topics are not promoted or labeled as verified relationships.
    Rotate vocabulary across daily runs so the search does not get stuck.
    """
    entity = str(row.get("name") or "").strip()
    if not entity or limit <= 0:
        return []
    topics = _topics(row)
    if not topics:
        topics = ["cybersecurity", "networking", "cloud"]
    topics = topics[rotation % len(topics):] + topics[:rotation % len(topics)]
    targets = list(dict.fromkeys(target_fields))
    queries: list[str] = []
    def add(value: str) -> None:
        if value and value not in queries:
            queries.append(value)

    if section == "manufacturers" and "competitors" in targets:
        # Reserve dedicated vendor-discovery routes, even if the field is empty.
        topic = topics[0]
        add(f'"{entity}" "{topic}" competing vendors alternatives')
        add(f'"{entity}" "{topic}" competidores fabricantes alternativas')
        add(f'"{entity}" "{topic}" concorrentes fornecedores comparativo')
        for candidate in _texts((row.get("fields") or {}).get("competitors"), limit=3):
            if candidate.casefold() != entity.casefold():
                add(f'"{entity}" vs "{candidate}" "{topic}" comparison')
        for offset, context in enumerate(SOURCE_VARIANTS):
            add(f'"{entity}" "{topics[offset % len(topics)]}" {context}')

    for idx, field in enumerate(targets):
        intents = HIGH_VALUE_FIELDS.get(field)
        if not intents:
            continue
        context = topics[(idx + rotation) % len(topics)]
        for offset, intent in enumerate(intents):
            add(f'"{entity}" "{context}" {intent}')
    return queries[:limit]
