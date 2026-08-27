# Westcon Iberia Decision Intelligence v3.3.2

## Objetivo
La v3.3.2 convierte la cobertura de ecosistema en una métrica persistente y dirigida por valor. El foco ya no es lanzar más búsquedas, sino transformar relaciones probables en relaciones demostradas y conocer con mucha más profundidad a los actores que realmente importan para Westcon Iberia.

## Cambios principales

- **Evidencia dirigida acumulativa**: una ejecución `daily` ya no puede borrar la profundidad obtenida en una `weekly` o `monthly`. `data/v33/targeted_evidence.json` conserva evidencia deduplicada con `first_seen_at`, `last_seen_at` y `seen_count`.
- **Tiering T1/T2/T3**: cada mayorista e integrador recibe una profundidad recomendada de investigación. T1 exige cobertura mucho mayor que T3.
- **Objetivo y gap de cobertura**: cada perfil publica `coverage_target`, `coverage_gap` y `coverage_attainment`.
- **Planificador adaptativo por deuda de conocimiento**: prioriza campos vacíos, distancia al objetivo, tier, relevancia para Westcon y prioridad comercial/competitiva.
- **Más presupuesto de verificación de relaciones**: pair verification representa 25% daily, 38% weekly y 45% monthly.
- **Intensidad de relación**: separa `¿la relación existe?` de `¿cuán fuerte parece ser?`. La intensidad combina número/diversidad de evidencias, fuente oficial, certificaciones/casos y confianza.
- **Cola explícita de verificación**: `data/v33/relationship_verification_queue.json` ordena relaciones probables y whitespace que necesitan corroboración.
- **Consolidación conservadora de duplicados exactos**: solo se fusionan entidades cuyo nombre normalizado es exactamente igual; nunca se hace fuzzy merge.
- **Cobertura por tier** en `coverage_report.json`.
- **UI**: nuevas columnas explicables para tier, objetivo de cobertura, información que falta, relaciones confirmadas/probables e intensidad máxima de relación.

## Interpretación de tiers

- **T1 — Estratégico**: alta relevancia o impacto potencial para Westcon Iberia. Objetivo de cobertura alto.
- **T2 — Relevante**: actor que merece seguimiento sistemático y profundidad selectiva.
- **T3 — Long tail**: vigilancia y cobertura de gaps de alto valor, evitando consumir presupuesto desproporcionado.

Los tiers son una prioridad de investigación, no una segmentación comercial ni una estimación de facturación.

## Nuevos datasets/campos

- `data/v33/relationship_verification_queue.json`
- `ecosystem_profiles.json`: `entity_tier`, `tier_score`, `coverage_target`, `coverage_gap`, `coverage_attainment`, contadores de relaciones e intensidad máxima.
- `integrator_vendor_matrix.json`: `relationship_intensity`, `official_evidence_count`.
- `distributor_vendor_matrix.json`: `relationship_intensity`, `official_evidence_count`.

## Instalación

Copiar el contenido sobre el repositorio actual y ejecutar:

```powershell
python tools/aplicar_v332.py
Get-Content VERSION
python tests/test_v332_unittest.py
node --check assets/v332/ecosystem-intelligence.js
```

Debe mostrar `3.3.2`.

Primera validación recomendada, reutilizando v3.2:

```powershell
python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32
```

Después puede ejecutarse una weekly para medir reducción real de `coverage_gap` y conversión de `probable/research` a `confirmed`.
