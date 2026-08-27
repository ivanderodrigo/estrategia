# Westcon Iberia Decision Intelligence v3.2.7

Hotfix de interfaz sobre v3.2.6. No modifica el motor de investigación ni los datasets.

## Cambio principal
Las vistas **Mayoristas** e **Integradores** dejan de depender de tarjetas como vista principal y pasan a mostrar tablas nativas, ordenables y configurables, visualmente alineadas con **Fabricantes**.

### Mayoristas
- Mayorista
- ámbito
- fabricantes / portfolio
- solape con Westcon
- servicios / fortalezas
- presión competitiva v3.2
- evidencias
- confianza
- última evidencia

### Integradores
- Integrador
- ámbito
- fabricantes asociados
- certificaciones / skills
- verticales
- presión competitiva v3.2
- whitespace de investigación
- confianza
- última evidencia
- campos opcionales: clientes, capacidad y evidencias

Al pulsar una fila se abre el detalle con evidencias, presión competitiva y, para integradores, candidatos de whitespace explícitamente marcados como **investigación no afirmada**.

La capa usa `data/v31/entity_intelligence.json`, `data/v32/competitive_pressure.json` y `data/v32/whitespace_candidates.json`.
