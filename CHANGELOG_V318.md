# CHANGELOG v3.18.0

## Decision Intelligence engine
- Añadido grafo canónico de entidades/relaciones con IDs estables y aliases.
- Propagación bidireccional de relaciones a partir de evidencias existentes y nuevas.
- Añadidas 9 line cards investigadas durante la release y 169 fabricantes extraídos de ellas.
- Añadidas 465 relaciones confirmadas Mayorista×Fabricante en el grafo y 493 Fabricante×Integrador confirmadas.
- Añadidas 191 relaciones Cliente×Tecnología como señales, sin elevarlas a hechos.

## Frontend
- Unificado comportamiento de tablas.
- Corregido bug de Clientes que impedía rerender tras mover/ordenar columnas.
- Resize, hide/show, persistencia y restauración por tabla.
- Reordenación de esquemas de Mayoristas y Clientes.

## Calidad
- Nuevo validador v3.18.
- Nuevo test suite v3.18.
- Auditor de referencias en workflows.
- Comstor/Forescout/duplicados de tipo cubiertos por tests.

## Research KPI
- Evidencias: 15.357 → 19.793.
- Relaciones: 1.198 → 1.792.
- Evidencia oficial: 7.140 → 10.766.
- Gaps: 1.627 → 1.615.
