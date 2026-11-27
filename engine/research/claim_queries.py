"""Search-language translation for historical labels (never evidence itself)."""

from __future__ import annotations

from ..model import canonical


SERVICE_RELATION_CUES = {
    "integracion de soluciones": (
        r"(?:integra[a-z]*|integrac[a-z]*|integrat[a-z]*|"
        r"implement[a-z]*|implant[a-z]*|deploy[a-z]*|"
        r"desplieg[a-z]*|despleg[a-z]*)"
    ),
    "suministro reventa": (
        r"(?:resell[a-z]*|resal[a-z]*|revend[a-z]*|"
        r"distribu[a-z]*|suministr[a-z]*|venta[s]?|"
        r"sales|suppl[a-z]*)"
    ),
    "servicios gestionados": (
        r"(?:managed|managing|manage[a-z]*|management|"
        r"gestion[a-z]*|administra[a-z]*)"
    ),
}


SERVICE_SEARCH_CONTEXT = {
    "integracion de soluciones": '(integration OR integración OR implementación)',
    "suministro reventa": '(reseller OR distribuidor OR suministro)',
    "servicios gestionados": '("managed services" OR "servicios gestionados")',
}


def service_template_parts(value: object, field: str = "services") -> tuple[str, str] | None:
    """Recognize exactly the historical taxonomy label + middle-dot + vendor."""
    raw = str(value or "").strip()
    if field != "services" or raw.count("·") != 1:
        return None
    left, right = raw.split("·", 1)
    prefix = canonical(left)
    vendor = canonical(right)
    if prefix not in SERVICE_RELATION_CUES or not 3 <= len(vendor) <= 90:
        return None
    return prefix, right.strip()


def claim_search_query(entity: str, field: str, value: object, *, context: str = "", site: str = "") -> str:
    """Use a vendor+relation query for a synthetic label, never a literal quote.

    Search results remain discovery leads; fetched page content is separately
    matched and attributed before any historical value can be accredited.
    """
    template = service_template_parts(value, field)
    if template:
        relation, vendor = template
        query = f'"{entity}" "{vendor}" {SERVICE_SEARCH_CONTEXT[relation]}'
    else:
        query = f'"{entity}" "{str(value).strip()}"'
    if context and not template:
        query += f" {context}"
    if site:
        query += f" site:{site}"
    return query
