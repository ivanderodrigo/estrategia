# WESTCON IBERIA DECISION INTELLIGENCE — v3.20.0 Production Candidate

Plataforma de inteligencia de negocio para España y Portugal. Principio rector: **hipersofisticada por dentro; extremadamente sencilla por fuera**.

## Arquitectura canónica

- `engine/`: modelo, entity resolution, enriquecimiento, grafo, gaps, métricas, calidad, publicación y research.
- `engine/research/`: planificación adaptativa y crawler web orientado a evidencia.
- `config/current/`: configuración/curación vigente y seed canónico de relaciones.
- `data/current/`: verdad interna; no se publica en GitHub Pages.
- `data/public/`: proyección pública compacta por secciones, cargada bajo demanda.
- `assets/app/`: único frontend.

No existe una cadena runtime `vXXX`. Git conserva el histórico; producción solo depende de la arquitectura canónica actual.

## Qué cambia en v3.20

1. Research de **todas las áreas**, priorizando Integradores y Mayoristas por deuda y yield.
2. HTTP 200 deja de significar «éxito de investigación». Se separan fetch, relevancia, candidatos, evidencia aceptada, campos enriquecidos y gaps cerrados.
3. Checkpoint + aislamiento en subproceso: el supervisor puede cortar un crawler atascado sin perder checkpoints ni impedir build/validación.
4. Grafo como fuente de verdad, normalización de relaciones y propagación bidireccional.
5. Nueva proyección `data/public/`: el navegador ya no descarga ni expone el dataset interno.
6. Carga de secciones bajo demanda, manteniendo el mismo frontend ejecutivo.
7. Quality gate de datos + validación YAML real de GitHub Actions.
8. Workflows con `checkout@v5`, cache pip y mutex único para evitar publicaciones concurrentes.
9. Publicación automática segura: identidad de bot y rechazo de snapshots obsoletos si `main` cambia durante la investigación.

## Métricas v3.19 → v3.20

- Gaps: **1450 → 1398 (-52)**.
- Integradores: **737 → 687**.
- Relaciones canónicas: **1209 → 1251**.
- Fabricante×Integrador confirmadas: **285 → 299**.
- Fabricante×Mayorista confirmadas: **733 → 761**.
- Evidencias únicas: **1184 → 1218**.
- Calidad estructural: **100/100**, 0 errores.

## Validación local

```powershell
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_workflows.py
python scripts/validate.py
node --check assets/app/intelligence.js
node tests/ui_smoke_v320.js
```

## Research manual

```powershell
python scripts/research_supervisor.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts/research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

Los workflows programados publican únicamente inteligencia canónica validada. Una fuente caída no detiene el ciclo completo.
