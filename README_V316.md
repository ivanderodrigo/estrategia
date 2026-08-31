# Westcon Iberia Decision Intelligence v3.16.0

Production Candidate construido sobre la v3.15.0 validada. Mantiene el alcance completo y hace visibles todos los campos declarados. Cuando todavía no existe evidencia suficiente, la interfaz muestra `Por investigar`.

## Qué cambia

- Motor por gaps con 32 pases, búsqueda de contradicciones, consultas en español, portugués e inglés, reintentos, backoff, circuit breaker, límites por dominio, checkpoints y reanudación.
- Más de 500 valores añadidos y más de 350 campos antes vacíos cubiertos entre evidencia directa y señales derivadas conservadoras.
- Semáforo vinculante: rojo para señales e indicios, amarillo para interpretaciones o corroboración parcial y verde solo para hechos oficiales o fuertemente corroborados.
- Confianza en el hecho, confianza en la interpretación y riesgo de acción separados.
- Métricas comparables v3.15 frente a v3.16 con una definición fija de gap.
- Todos los campos del esquema siguen visibles. No se eliminan columnas para mejorar cobertura.

## Instalación completa

1. Descomprime `Westcon_v3.16.0_Production_Candidate.zip` en una carpeta nueva.
2. Entra en la carpeta.
3. Ejecuta `python scripts/research_supervisor_v316.py --profile daily --skip-v33`.
4. Abre la aplicación con el servidor local descrito más abajo.

## Actualización segura desde v3.15.0

Descomprime `Westcon_v3.16.0_UPDATE_ONLY.zip` y ejecuta:

```powershell
python aplicar_v316.py --repo "C:\Users\ivand\Downloads\estrategia"
```

El instalador comprueba la versión base, conserva `.git`, copia únicamente el manifiesto, ejecuta pruebas y validación y revierte los archivos si algo falla. No crea commits ni hace push.

## Validación exacta

```bash
python -m py_compile scripts/v316/*.py scripts/research_supervisor_v316.py
python -m unittest tests/test_v316.py -v
python scripts/v316/validate_v316.py
node --check assets/v316/intelligence.js
node tests/ui_smoke_v316.js
```

## Ciclos de investigación

```bash
python scripts/research_supervisor_v316.py --profile daily --max-runtime 720
python scripts/research_supervisor_v316.py --profile weekly --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor_v316.py --profile monthly --max-runtime 3300 --fallback-runtime 300
```

Para reconstruir desde la evidencia ya disponible, sin lanzar la base de investigación de red:

```bash
python scripts/research_supervisor_v316.py --profile daily --skip-v33
```

## Prueba local

```bash
python -m http.server 8000
```

Abre `http://localhost:8000/`. Comprueba las seis vistas, filtros, detalle de trazabilidad, estado, fuentes y exportación.

## Git, solo cuando decidas publicar

El instalador no toca el historial. Tras revisar los cambios:

```bash
git status --short
git add .
git commit -m "Release Westcon Decision Intelligence v3.16.0"
git push origin HEAD
```

## Informes

- `data/v316/metrics_before_after.json`
- `data/v316/research_gaps.json`
- `data/v316/source_report.json`
- `data/v316/coverage_report.json`
- `docs/v316/QUALITY_AUDIT_V316.md`
- `docs/v316/TEST_REPORT_V316.md`
