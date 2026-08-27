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
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    intelligence_path = root / "data/v35/intelligence.json"
    if not intelligence_path.exists():
        return ["falta data/v35/intelligence.json"]
    try:
        data = _load(intelligence_path)
    except Exception as exc:
        return [f"intelligence.json inválido: {exc}"]

    if data.get("meta", {}).get("version") != "3.5.0":
        errors.append("la versión pública no es 3.5.0")

    minimums = {"manufacturers": 30, "integrators": 20, "distributors": 8, "trends": 12, "architectures": 8}
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

    for row in data.get("distributors") or []:
        if "westcon" in str(row.get("name") or "").lower():
            errors.append("Westcon aparece como mayorista competidor")

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
    if len(source_catalog) < 180:
        errors.append(f"catálogo de fuentes demasiado estrecho ({len(source_catalog)})")
    source_ids = {str(row.get("id") or "") for row in source_catalog}
    missing_sources = sorted(REQUIRED_SOURCES - source_ids)
    if missing_sources:
        errors.append("faltan familias de fuente clave: " + ", ".join(missing_sources))

    index_path = root / "index.html"
    js_path = root / "assets/v350/intelligence.js"
    css_path = root / "assets/v350/intelligence.css"
    for path in (index_path, js_path, css_path):
        if not path.exists():
            errors.append(f"falta activo frontend: {path.relative_to(root)}")
    if index_path.exists():
        index = index_path.read_text(encoding="utf-8")
        views = re.findall(r'data-view="([^"]+)"', index)
        expected = ["fabricantes", "integradores", "mayoristas", "tendencias", "arquitecturas"]
        if views != expected:
            errors.append(f"navegación principal incorrecta: {views}")
        if "assets/v350/intelligence.js" not in index or "assets/v350/intelligence.css" not in index:
            errors.append("index.html no carga exclusivamente la capa v3.5 esperada")
        if re.search(r"assets/(?:v31|v32|v33|v333|v340)/", index, re.I):
            errors.append("index.html carga activos legacy")

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
    print("VALIDACIÓN v3.5.0 · PASS")
