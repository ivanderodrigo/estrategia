# Westcon Iberia Decision Intelligence v3.15.0

Production Candidate construido sobre v3.14.0. Mantiene el alcance completo y hace visibles todos los campos declarados. Cuando todavía no existe evidencia suficiente, la interfaz muestra `Por investigar`.

## Qué cambia

- Motor por gaps con 15 pases, consultas en español, portugués e inglés, reintentos, backoff, circuit breaker, límites por dominio, checkpoints y reanudación.
- 66 rutas públicas nuevas y 124 valores nuevos investigados, con etiquetas separadas para hecho, señal e interpretación.
- Confianza en el hecho, confianza en la interpretación y riesgo de acción separados.
- Métricas comparables v3.14 frente a v3.15 con una definición fija de gap.
- Todos los campos del esquema siguen visibles. No se eliminan columnas para mejorar cobertura.

## Instalación completa

1. Descomprime `Westcon_v3.15.0_Production_Candidate.zip` en una carpeta nueva.
2. Entra en la carpeta.
3. Ejecuta `python scripts/research_supervisor_v315.py --profile daily --skip-v33`.
4. Abre la aplicación con el servidor local descrito más abajo.

## Actualización segura desde v3.14.0

Descomprime `Westcon_v3.15.0_UPDATE_ONLY.zip` y ejecuta:

```powershell
python aplicar_v315.py --repo "C:\Users\ivand\Downloads\estrategia"
```

El instalador comprueba la versión base, conserva `.git`, copia únicamente el manifiesto, ejecuta pruebas y validación y revierte los archivos si algo falla. No crea commits ni hace push.

## Validación exacta

```bash
python -m py_compile scripts/v315/*.py scripts/research_supervisor_v315.py
python -m unittest tests/test_v315.py -v
python scripts/v315/validate_v315.py
node --check assets/v315/intelligence.js
node tests/ui_smoke_v315.mjs
```

## Ciclos de investigación

```bash
python scripts/research_supervisor_v315.py --profile daily --max-runtime 720
python scripts/research_supervisor_v315.py --profile weekly --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor_v315.py --profile monthly --max-runtime 3300 --fallback-runtime 300
```

Para reconstruir desde la evidencia ya disponible, sin lanzar la base de investigación de red:

```bash
python scripts/research_supervisor_v315.py --profile daily --skip-v33
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
git commit -m "Release Westcon Decision Intelligence v3.15.0"
git push origin HEAD
```

## Informes

- `data/v315/metrics_before_after.json`
- `data/v315/research_gaps.json`
- `data/v315/source_report.json`
- `data/v315/coverage_report.json`
- `docs/v315/QUALITY_AUDIT_V315.md`
- `docs/v315/TEST_REPORT_V315.md`
