from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SECTIONS = ("manufacturers", "integrators", "distributors", "trends", "architectures")
BANNED_SCHEMA_FRAGMENTS = ("priority", "tier", "activation", "response", "depth", "decision", "action", "recommend")
REQUIRED_SOURCES = {
    "gartner_public", "idc_public", "forrester_public",
    "linkedin_jobs_public", "infojobs_es", "indeed_public", "glassdoor_public", "tecnoempleo_es",
    "official_careers", "employer_ats", "vendor_partner_locators", "distributor_linecards",
    "integrator_case_studies", "placsp", "base_portugal", "ted_api",
    "vendor_partner_locators_iberia", "vendor_reseller_msp_directories", "partner_jobs_linkedin",
    "nist_zero_trust", "gartner_architecture_public", "forrester_architecture_public", "idc_europe_public",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    intelligence_path = root / "data/v38/intelligence.json"
    if not intelligence_path.exists():
        return ["falta data/v38/intelligence.json"]
    try:
        data = _load(intelligence_path)
    except Exception as exc:
        return [f"intelligence.json inválido: {exc}"]

    if data.get("meta", {}).get("version") != "3.8.2":
        errors.append("la versión pública no es 3.8.2")

    minimums = {"manufacturers": 36, "integrators": 30, "distributors": 8, "trends": 15, "architectures": 10}
    for section in SECTIONS:
        rows = data.get(section) or []
        if len(rows) < minimums[section]:
            errors.append(f"{section}: cobertura insuficiente ({len(rows)})")
        for row in rows:
            if not (row.get("evidence") or []):
                errors.append(f"{section}/{row.get('name')}: entidad o título sin trazabilidad")
            for field_id, value in (row.get("fields") or {}).items():
                if not isinstance(value, dict) or value.get("value") in (None, "", [], {}):
                    errors.append(f"{section}/{row.get('name')}/{field_id}: campo vacío publicado")
                    continue
                evidence = value.get("evidence") or []
                if not evidence:
                    errors.append(f"{section}/{row.get('name')}/{field_id}: campo sin trazabilidad")
                for item in evidence:
                    if not (item.get("source") or item.get("title")):
                        errors.append(f"{section}/{row.get('name')}/{field_id}: evidencia sin identificación")
                if isinstance(value.get("value"), list) and value.get("items"):
                    for atom in value.get("items") or []:
                        if not atom.get("evidence"):
                            errors.append(f"{section}/{row.get('name')}/{field_id}: etiqueta sin fuente propia")
                        score=atom.get("confidence")
                        if score is None or not (0 <= float(score) <= 1):
                            errors.append(f"{section}/{row.get('name')}/{field_id}: etiqueta sin confianza numérica 0–1")
                        if atom.get("confidence_band") not in {"high","medium","low"}:
                            errors.append(f"{section}/{row.get('name')}/{field_id}: etiqueta sin banda de confianza")
                        if atom.get("confidence_band") in {"medium", "low"} and not atom.get("confidence_factors"):
                            errors.append(f"{section}/{row.get('name')}/{field_id}: etiqueta media/baja sin razones explícitas de confianza")

    internal_distributor_tokens = ("westcon", "comstor")
    for row in data.get("distributors") or []:
        name = str(row.get("name") or "").lower()
        if any(token in name for token in internal_distributor_tokens):
            errors.append(f"unidad interna Westcon aparece como mayorista competidor: {row.get('name')}")
    for row in data.get("manufacturers") or []:
        dist_field = ((row.get("fields") or {}).get("distributors") or {})
        for value in dist_field.get("value") or []:
            text = str(value).lower()
            if any(token in text for token in internal_distributor_tokens):
                errors.append(f"fabricantes/{row.get('name')}: unidad interna Westcon publicada como mayorista alternativo: {value}")

    # Fabricantes: solo portfolio Westcon como filas. Los competidores viven como contexto trazable.
    portfolio = _load(root / "data/vendor_intelligence.json").get("vendors", [])
    expected_vendors = {str(x.get("name")) for x in portfolio}
    published_vendors = {str(x.get("name")) for x in data.get("manufacturers") or []}
    if published_vendors != expected_vendors:
        errors.append(f"fabricantes: las filas no coinciden exactamente con el portfolio Westcon ({len(published_vendors)} vs {len(expected_vendors)})")
    for row in data.get("manufacturers") or []:
        if "portfolio_role" in (row.get("fields") or {}) or "portfolio_compared" in (row.get("fields") or {}):
            errors.append(f"fabricantes/{row.get('name')}: conserva campos legacy de clasificación de filas")

    # Architecture taxonomy guard: UiPath is automation/orchestration, not an Identity platform.
    for arch in data.get("architectures") or []:
        for layer in ((arch.get("fields") or {}).get("layers") or {}).get("value", []) or []:
            if "identity" in str(layer.get("layer") or "").lower() and "UiPath" in (layer.get("vendors") or []):
                errors.append(f"arquitecturas/{arch.get('name')}: UiPath aparece indebidamente en una capa Identity")
        for vendor in ((arch.get("fields") or {}).get("vendors") or {}).get("value", []) or []:
            if vendor not in expected_vendors:
                errors.append(f"arquitecturas/{arch.get('name')}: fabricante fuera del portfolio: {vendor}")

    # Trends must be substantially richer than v3.5.
    required_trend_fields = {"domain","observed","trend_market_metrics","adjacent_market_metrics","horizon","drivers","buyer_priorities","market_players","westcon_vendors","evolution","iberia_context","sources"}
    for row in data.get("trends") or []:
        missing = required_trend_fields - set((row.get("fields") or {}).keys())
        if missing:
            errors.append(f"tendencias/{row.get('name')}: faltan dimensiones: {', '.join(sorted(missing))}")
    metric_coverage = sum("trend_market_metrics" in (row.get("fields") or {}) for row in data.get("trends") or [])
    if metric_coverage < 10:
        errors.append(f"tendencias: cobertura de métricas de mercado insuficiente ({metric_coverage})")
    player_coverage = sum("market_players" in (row.get("fields") or {}) for row in data.get("trends") or [])
    if player_coverage < 10:
        errors.append(f"tendencias: cobertura de panorama de fabricantes insuficiente ({player_coverage})")

    schemas = data.get("schemas") or {}
    for section in SECTIONS:
        schema = schemas.get(section) or []
        for col in schema:
            field_id = str(col.get("id") or "").lower()
            if any(fragment in field_id for fragment in BANNED_SCHEMA_FRAGMENTS):
                errors.append(f"{section}: columna interna/no final publicada: {field_id}")
            if col.get("clarify") and not str(col.get("help") or "").strip():
                errors.append(f"{section}/{field_id}: columna marcada con ? sin aclaración")

    source_catalog = data.get("source_catalog") or []
    if len(source_catalog) < 200:
        errors.append(f"catálogo de fuentes demasiado estrecho ({len(source_catalog)})")
    source_ids = {str(row.get("id") or "") for row in source_catalog}
    missing_sources = sorted(REQUIRED_SOURCES - source_ids)
    if missing_sources:
        errors.append("faltan familias de fuente clave: " + ", ".join(missing_sources))

    index_path = root / "index.html"
    js_path = root / "assets/v382/intelligence.js"
    css_path = root / "assets/v382/intelligence.css"
    for path in (index_path, js_path, css_path):
        if not path.exists():
            errors.append(f"falta activo frontend: {path.relative_to(root)}")
    if index_path.exists():
        index = index_path.read_text(encoding="utf-8")
        views = re.findall(r'data-view="([^"]+)"', index)
        expected = ["fabricantes", "integradores", "mayoristas", "tendencias", "arquitecturas"]
        if views != expected:
            errors.append(f"navegación principal incorrecta: {views}")
        if "assets/v382/intelligence.js" not in index or "assets/v382/intelligence.css" not in index:
            errors.append("index.html no carga exclusivamente la capa v3.8 esperada")
        if re.search(r"assets/(?:v31|v32|v33|v333|v340)/", index, re.I):
            errors.append("index.html carga activos legacy")
        for control in ("textSmaller", "textReset", "textLarger"):
            if f'id="{control}"' not in index:
                errors.append(f"interfaz: falta control de tamaño de texto {control}")

    # The active user-facing product must not contain action/advice vocabulary inherited from v3.4.
    for path in (index_path, js_path, intelligence_path):
        if path.exists() and re.search(r"\brecomend(?:acion|ación|aciones|ar|ation|ations)\b", path.read_text(encoding="utf-8"), re.I):
            errors.append(f"{path.relative_to(root)} contiene lenguaje de recomendación en el producto activo")

    return errors


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[2]
    errors = validate(root)
    if errors:
        for error in errors:
            print("ERROR ·", error)
        raise SystemExit(1)
    print("VALIDACIÓN v3.8.2 · PASS")
