# Auditoría técnica — v3.20.0

## Resultado
**Quality score: 100/100 · errores: 0 · warnings: 0.**

## KEEP
- Arquitectura canónica `engine/`, `config/current/`, `data/current/`, `assets/app/`.
- Grafo canónico y trazabilidad campo→evidencia.
- Motor común de tablas (Fabricantes, Integradores, Mayoristas y Clientes).

## CONSOLIDATE
- Research: un único planner/crawler transversal sustituye al crawler específico de Mayoristas.
- Publicación: `data/public` es el único contrato de datos del navegador.
- Relaciones: una arista canónica multi-scope, no copias independientes por tabla/país.

## MIGRATE
- `migrated_relationships.json` → `relationship_seed.json`.
- `distributor_research.json` → `curated_distributors.json`, consumido explícitamente por el pipeline.
- UI de `data/current` → proyección pública fragmentada.

## REMOVE
- `engine/research/distributor_web.py`.
- tests/smoke específicos v3.19 sustituidos por v3.20.
- Dependencia de `checkout@v4`.

## REVIEW
- Los 1398 gaps restantes siguen siendo deuda real; no se cierran por semántica ni ausencia superficial de resultados.
- La mayor bolsa sigue en Integradores (687); el nuevo planner la prioriza automáticamente.
