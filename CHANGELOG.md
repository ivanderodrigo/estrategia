# CHANGELOG — v3.19.0 Production Candidate

Fecha: 2026-08-31

## Inteligencia

- Investigación web-first de Mayoristas con prioridad a dominio oficial, line card, catálogo, vendors, PDF, servicios y careers.
- Mayoristas: 355 → 190 gaps.
- Huecos competitivos clave: 172 → 24.
- 52 line cards con evidencia suficiente; 793 menciones de fabricante y 516 nombres de fabricante distintos en line cards confirmados.
- Propagación Mayorista ↔ Fabricante mediante grafo canónico.
- 733 relaciones Fabricante × Mayorista confirmadas.

## Arquitectura

- Runtime único `current`; eliminadas dependencias activas de `assets/data/config/scripts/vXXX`.
- Grafo con una arista canónica por A–relación–B y scopes geográficos agregados.
- Migración única de relaciones v3.18 a `config/current/migrated_relationships.json` sin dependencia runtime de `data/v318`.
- Plan de investigación normalizado: los 48 pasos se generan bajo demanda y dejan de repetirse dentro de cada gap; `research_gaps.json` baja a ~1 MB.
- Publicación Pages limitada a `intelligence.json` + `last_run.json`; ledger, learning y cola quedan internos.
- Un único motor de tabla para Fabricantes, Integradores, Mayoristas y Clientes con drag/drop, sort, resize, hide/show y persistencia.

## Calidad

- Entity resolution: Arrow Electronics→Arrow ECS, Digicomp→CloudIT, aliases Palo Alto/PANW, HPE, TD SYNNEX/Tech Data y NEXUS/Soon.
- Tests de Comstor, Forescout, fabricantes-mal-clasificados, aliases, evidencia, guiones, grafo, runtime legacy, workflows y tabla común.
- UPDATE_ONLY transaccional desde v3.18.0, preserva `.git`, no hace commit/push y restaura baseline si falla una validación.


## Packaging hotfix · Windows UTF-8
- Tests and validators now declare UTF-8 explicitly for all text reads/writes.
- Prevents Python on Windows from falling back to cp1252 when reading canonical JSON.
- Added regression test `tests/test_encoding_windows.py`.
