# Westcon Iberia Decision Intelligence v3.2.1

Hotfix de endurecimiento de Evidence Fabric sobre v3.2.0.

## Objetivos

- TED deja de lanzar una consulta por entidad: hace dos pulls acotados (España y Portugal) y resuelve entidades localmente.
- TED expone errores HTTP/sintaxis en `source_health.json` y en la línea final.
- PLACSP prueba host actual + fallback histórico oficial y analiza el texto completo de cada entrada Atom, no solo `title/summary`.
- Generic feeds añade autodiscovery `<link rel="alternate">` desde la home y métricas reales de fuentes probadas/fallidas.
- CISA KEV deja de etiquetarse como `security_incident`: usa `known_exploited_vulnerability`.
- El grafo usa evidencia estructurada (`buyer_name`, `winner_name`, `product`, `cve`) para crear más relaciones útiles.
- Las KEV de fabricantes Westcon pueden generar oportunidad de assessment/hardening/managed security cuando superan materialidad/confianza/relevancia.
- Se añaden métricas de candidatos, deduplicación y errores de conectores.

## Validación local

```powershell
python tests/test_v320_unittest.py
python tests/test_v321_unittest.py
python scripts/research_supervisor_v32.py --profile daily --max-runtime 180 --skip-v31
```

No hacer `git push` hasta revisar la línea final y una muestra de `decisions.json` / `events.json`.
