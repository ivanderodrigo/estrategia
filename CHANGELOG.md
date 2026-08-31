# CHANGELOG — v3.20.0 Production Candidate

## Arquitectura
- Research generalizado y orientado a yield (`planner.py` + `web_intelligence.py`).
- Nueva capa `enrichment.py`, auditor `quality.py` y proyección `publication.py`.
- `relationship_seed.json` reemplaza nombres de migración históricos dentro del runtime actual.
- Curación vigente separada en `curated_distributors.json` y `curated_intelligence.json`.
- Retirado el crawler específico `distributor_web.py` y los tests v3.19 del runtime actual.

## Inteligencia
- Gaps totales: 1450 → 1398.
- Integradores: 737 → 687 gaps.
- Relaciones canónicas: 1209 → 1251.
- Fabricante×Integrador: 285 → 299 confirmadas.
- Fabricante×Mayorista: 733 → 761 confirmadas.
- Nuevas evidencias oficiales verificadas para VASS, NTT DATA, Minsait, Orange Cyberdefense, Econocom, Bechtle, Warpcom, Timestamp, S21sec, Integrity360, Capgemini, Atos y SEIDOR, entre otras.

## Frontend
- Misma experiencia visual; datasets públicos por sección cargados bajo demanda.
- El navegador deja de consumir `data/current/intelligence.json`.
- Exportaciones cargan todas las secciones solo cuando son necesarias.

## Operación
- Workflows YAML validados de verdad con PyYAML.
- `actions/checkout@v5`, cache pip y lock único de research.
- Supervisor con hard timeout por subproceso y checkpoint durable.
- Publisher con identidad `github-actions[bot]` y protección contra snapshots stale.
