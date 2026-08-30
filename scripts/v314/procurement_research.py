#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from v32.direct_sources import atom_feed, ted_search  # noqa: E402

VERSION = "3.13.0"


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _exact_url(url: str, source_id: str) -> bool:
    u = str(url or "").strip()
    if not u.startswith("http"):
        return False
    host = urlparse(u).netloc.casefold()
    if source_id == "ted":
        return "ted.europa.eu" in host and "/notice/-/detail/" in u
    if source_id.startswith("placsp"):
        if not any(x in host for x in ("contrataciondelestado.es", "contrataciondelsectorpublico.gob.es")):
            return False
        low = u.casefold()
        # Reject obvious generic landing/feed endpoints; accept the deep link/id emitted by the official Atom entry.
        return not any(x in low for x in ("/datosabiertos", "licitacionesperfilescontratantecompleto", "plataformasagregadassinmenores"))
    return False


def _area(title: str) -> str:
    t = str(title or "").casefold()
    rules = [
        (("ciber", "cyber", "security", "segurança", "siem", "soc", "firewall", "pam"), "Ciberseguridad"),
        (("network", "red ", "redes", "rede ", "wan", "lan", "wifi", "wi-fi", "comunicaciones"), "Networking / comunicaciones"),
        (("cloud", "nube", "nuvem", "saas", "azure", "microsoft 365"), "Cloud / servicios"),
        (("storage", "almacenamiento", "armazenamento", "backup", "servidor", "server", "datacenter", "data center"), "Data center / infraestructura"),
        (("observability", "observabilidad", "monitorización", "monitorizacao", "monitorização"), "Observabilidad / monitorización"),
        (("artificial intelligence", "inteligencia artificial", "inteligência artificial", " ai ", "machine learning"), "IA / automatización"),
        (("software", "licencia", "licence", "licenciamento", "aplicación", "aplicacao", "aplicação"), "Software / aplicaciones"),
    ]
    for terms, label in rules:
        if any(x in f" {t} " for x in terms):
            return label
    return "Tecnología / servicios TI"


def _notice_id(row: dict, source_id: str) -> str:
    for key in ("external_id", "contractId", "contract_id"):
        if row.get(key):
            return str(row[key]).strip()
    url = str(row.get("url") or "")
    if source_id == "ted" and "/detail/" in url:
        return url.rsplit("/detail/", 1)[-1].split("?", 1)[0]
    digest = hashlib.sha1(f"{url}|{row.get('title')}".encode("utf-8", errors="ignore")).hexdigest()[:14]
    return f"PLACSP-{digest}"


def _convert(row: dict, source_id: str, scope: str) -> dict | None:
    url = str(row.get("url") or "").strip()
    if not _exact_url(url, source_id):
        return None
    title = str(row.get("title") or "").strip()
    if not title:
        return None
    buyer = str(row.get("buyer_name") or row.get("buyer") or "").strip() or f"Organismo público · {scope}"
    published = str(row.get("published_at") or row.get("published") or "").strip()
    return {
        "notice_id": _notice_id(row, source_id),
        "scope": scope,
        "buyer": buyer,
        "title": title,
        "area": _area(title),
        "url": url,
        "source": "TED · Tenders Electronic Daily" if source_id == "ted" else "PLACSP · Plataforma de Contratación del Sector Público",
        "source_portal": "TED" if source_id == "ted" else "PLACSP",
        "date": published or datetime.now(timezone.utc).date().isoformat(),
        "confidence": 0.97 if source_id == "ted" else 0.96,
    }


def collect(profile: str = "daily", timeout: int = 20) -> dict:
    cfg = _load(ROOT / "config/v313/procurement_sources.json", {})
    notices: dict[str, dict] = {}
    diagnostics = []

    ted_cfg = next((x for x in cfg.get("sources", []) if x.get("id") == "ted_api"), {})
    if ted_cfg.get("url"):
        conn = {"url": ted_cfg["url"], "authority": .99}
        try:
            rows, diag = ted_search(conn, [], profile=profile if profile in {"daily", "weekly", "monthly"} else "weekly", timeout=timeout)
            diagnostics.append({"source": "ted", **diag})
            for row in rows:
                scope = str(row.get("country") or "").upper()
                if scope not in {"ES", "PT"}:
                    continue
                item = _convert(row, "ted", scope)
                if item:
                    notices[f"TED:{item['notice_id']}"] = item
        except Exception as exc:
            diagnostics.append({"source": "ted", "error": f"{type(exc).__name__}: {exc}"})

    source_registry = [
        {"id": "placsp_profiles", "name": "PLACSP · Perfiles de contratante", "category": "official", "authority": .98},
        {"id": "placsp_aggregated", "name": "PLACSP · Plataformas agregadas", "category": "official", "authority": .97},
    ]
    cache_dir = ROOT / "data/v314/.procurement_cache"
    for source in cfg.get("sources", []):
        sid = str(source.get("id") or "")
        if not sid.startswith("placsp") or not source.get("url"):
            continue
        conn = {"source_id": sid, "url": source["url"], "country": "ES", "authority": .98}
        try:
            rows, diag = atom_feed(conn, source_registry, [], timeout=timeout, state_dir=cache_dir, profile=profile if profile in {"daily", "weekly", "monthly"} else "weekly")
            diagnostics.append({"source": sid, **diag})
            for row in rows:
                item = _convert(row, sid, "ES")
                if item:
                    notices[f"{sid}:{item['notice_id']}"] = item
        except Exception as exc:
            diagnostics.append({"source": sid, "error": f"{type(exc).__name__}: {exc}"})

    max_rows = int(cfg.get("max_rows") or 800)
    values = sorted(notices.values(), key=lambda x: str(x.get("date") or ""), reverse=True)[:max_rows]
    return {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "notices": values,
        "diagnostics": diagnostics,
        "policy": "Solo se publican registros con enlace exacto al anuncio/expediente oficial; los enlaces genéricos del portal se descartan.",
    }


def run(profile: str = "daily", timeout: int = 20) -> dict:
    path = ROOT / "data/v314/procurement_live.json"
    previous = _load(path, {})
    result = collect(profile, timeout)
    # A temporary source outage must never erase the last valid live procurement cache.
    if not result.get("notices") and previous.get("notices"):
        result["notices"] = previous["notices"]
        result["cache_fallback"] = True
    _atomic_write(path, result)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Actualiza contratación tecnológica ES/PT con enlaces oficiales exactos")
    p.add_argument("--profile", default=os.environ.get("RESEARCH_PROFILE", "daily"), choices=["daily", "weekly", "monthly", "deep", "exhaustive"])
    p.add_argument("--timeout", type=int, default=20)
    args = p.parse_args()
    profile = {"deep": "weekly", "exhaustive": "monthly"}.get(args.profile, args.profile)
    result = run(profile, args.timeout)
    print(json.dumps({"version": VERSION, "live_notices": len(result.get("notices", [])), "cache_fallback": bool(result.get("cache_fallback")), "diagnostics": result.get("diagnostics", [])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
