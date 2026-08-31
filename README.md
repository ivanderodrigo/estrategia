# WESTCON IBERIA DECISION INTELLIGENCE — v3.19.0 Production Candidate

Arquitectura canónica y única para España y Portugal, orientada a inteligencia competitiva, trazabilidad y actualización incremental.

## Principio rector

**HIPERSOFISTICADA POR DENTRO. EXTREMADAMENTE SENCILLA POR FUERA.**

v3.19 elimina la dependencia de generaciones `vXXX` y consolida el runtime en:

- `engine/` — grafo, entity resolution, gaps, métricas y motor de investigación;
- `config/current/` — aliases, política y fuentes actuales;
- `data/current/` — única fuente activa de datos;
- `assets/app/` — frontend único;
- `scripts/` — supervisión, publicación y validación sin sufijos de versión.

## Resultado principal

- Gaps totales: **1615 → 1450 (10.22% menos)**.
- Mayoristas: **355 → 190 (46.5% menos)**.
- Gaps competitivos clave de Mayoristas (line card + overlap Westcon + no-Westcon + especialización): **172 → 24 (86.0% menos)**.
- Line cards con evidencia suficiente: **18/60 → 52/58**.
- Relaciones canónicas: **711 → 1209**. v3.18 tenía 1149 registros por país que canonicalizan a 711 aristas comparables.
- Relaciones Fabricante × Mayorista confirmadas: **236 → 733**.
- Fuentes: **386 → 504**; dominios únicos **194 → 226**.

## Semántica de evidencia

`CONFIRMADO`, `PROBABLE`, `SEÑAL` y `POR INVESTIGAR` siguen siendo estados distintos. Una vacante puede demostrar una skill o una señal tecnológica, pero nunca confirma por sí sola partnership o distribución. Una única estimación financiera secundaria no cierra automáticamente un gap de facturación.

## Ejecución

```powershell
python scripts\research_supervisor.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts\research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts\research_supervisor.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

Validación:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts\validate.py
node --check assets\app\intelligence.js
node tests\ui_smoke_v319.js
```

Consulta `docs/release/` para auditoría, métricas, gaps, fuentes, line cards, tests, instalación y deuda restante.
