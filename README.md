# Westcon Iberia Decision Intelligence v3.18.0 — Production Candidate

Construida exclusivamente sobre la baseline completa v3.17.0 contenida en el ZIP de entrada.

## Objetivo
Esta release introduce una fuente de verdad relacional canónica, propagación bidireccional de evidencias, investigación real de line cards oficiales y una infraestructura única de tablas para Fabricantes, Integradores, Mayoristas y Clientes.

## Cambios principales
- Grafo canónico `data/v318/relationship_graph.json` con entidades normalizadas, aliases y relaciones trazables.
- Propagación Mayorista ↔ Fabricante e Integrador ↔ Fabricante desde la misma evidencia.
- Investigación oficial incorporada para Arrow ECS, Exclusive Networks, Infinigate, Ingram Micro, TD SYNNEX, Aseminfor, Infortisa, Depau y DMI; enriquecimiento adicional de Ajoomal.
- Comparación de line cards contra portfolio Westcon: España excluye Proofpoint y Check Point; Portugal = España + Proofpoint + Check Point.
- Comstor excluido de competidores; Forescout fuera del portfolio Westcon.
- Componente común de tablas: drag/drop, sort, resize, hide/show, persistencia y restauración; corregido el rerender de Clientes.
- Orden por defecto de Mayoristas y Clientes orientado a comparación de negocio.
- Auditoría de workflows y test de referencias a scripts/validadores.
- Auditoría de repositorio con clasificación KEEP / REMOVE / CONSOLIDATE / MIGRATE / REVIEW.

## Validación
```powershell
python -m unittest tests/test_v318.py -v
python scripts/v318/validate_v318.py
python scripts/v318/audit_workflows.py
python scripts/test_resilience.py
python scripts/test_schedule.py
node --check assets/v318/intelligence.js
node tests/ui_smoke_v318.js
```

## Investigación
```powershell
python scripts/research_supervisor_v318.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts/research_supervisor_v318.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor_v318.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

## Limitación conocida principal
La release aumenta de forma muy fuerte la densidad relacional y la evidencia oficial, pero la reducción neta de gaps bajo la definición estricta v3.17→v3.18 es todavía de 12 gaps (0,74%). No se ha maquillado esta métrica cerrando huecos semánticamente. Véase `docs/v318/GAPS_BEFORE_AFTER.md`.
