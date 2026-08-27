# Westcon Iberia Decision Intelligence v3.2.3

## Signal Quality + Economic Prioritization

v3.2.3 endurece la v3.2.2 sin volver a inflar el número de señales. El objetivo es que una evidencia verdadera solo se convierta en decisión cuando además tenga **fit tecnológico**, **relevancia Westcon Iberia**, **materialidad**, **confianza** y una lógica económica defendible.

### Cambios principales

- **Procurement fit independiente**: una licitación de software genérico o puesto de trabajo TIC se conserva como evidencia, pero no se eleva automáticamente a oportunidad. Networking, Cybersecurity, SASE/SSE, Cloud, Data Center, AI, Observability, Automation e Identity reciben mayor fit.
- **Generic feed flood control**: límite por feed y perfil, ventana de frescura y eliminación del fallback de `channel_media -> Iberia Technology Market` sin entidad concreta. Los medios siguen sirviendo para descubrir entidades, no para inundar el mercado con señales sin sujeto.
- **Direct-row deduplication** antes de event intelligence.
- **Strategic fit** por evento y **evidence grade A/B/C/D**.
- **Materiality v2**: incorpora fit estratégico; las licitaciones market-level genéricas reciben una penalización adicional.
- **Decision gate v2**: P1/P2/P3/P4 requiere evidencia suficiente; oportunidades y amenazas sin fuente directa/corroboración se degradan a watch.
- **KEV**: no es una oportunidad comercial automática; se exige fit suficiente y señales de riesgo/explotación.
- **Economic prioritization** sin inventar euros: `revenue_potential`, `margin_potential`, `recurrence_potential`, `time_to_revenue_score`, `enablement_effort_score` y `economic_priority_score`. Es un proxy relativo hasta integrar pipeline/margen internos.
- **Competitive pressure**: `data/v32/competitive_pressure.json`.
- **Portfolio intelligence**: `data/v32/portfolio_intelligence.json`.
- **Whitespace research candidates**: `data/v32/whitespace_candidates.json`. Son hipótesis de investigación, nunca relaciones comerciales afirmadas sin evidencia.
- **Knowledge graph** amplía relaciones a dominios tecnológicos cuando no existe un objeto empresarial fiable.

### Filosofía

La aplicación debe preferir 15 decisiones defendibles a 100 recomendaciones ruidosas. Los datos históricos y de bajo fit siguen en el event store para investigación, pero no llegan a Dirección como acciones.

### Instalación

Copiar el contenido encima del repositorio v3.2.2 y ejecutar desde la raíz:

```powershell
python tools/aplicar_v323.py
Get-Content VERSION
```

Debe devolver `3.2.3`.

### Tests

```powershell
python tests/test_v320_unittest.py
python tests/test_v321_unittest.py
python tests/test_v322_unittest.py
python tests/test_v323_unittest.py
```

La nueva batería añade 6 tests y mantiene compatibilidad con las 45 comprobaciones anteriores: **51 tests** en total.

### Prueba corta

```powershell
python scripts/research_supervisor_v32.py --profile daily --max-runtime 180 --skip-v31
```

La salida añade:

- `direct rows kept/raw (dedup N)`
- `high-econ`
- `competitive entities`
- `whitespace research`

No se espera que aumenten necesariamente las decisiones. Se espera que mejoren el ratio de decisiones útiles, el balance opportunity/threat/watch y el fit económico.
