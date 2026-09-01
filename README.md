# Westcon Iberia Decision Intelligence — v4.0.4

Plataforma de inteligencia de negocio para el canal IT de España y Portugal. Su principio de diseño es: **hipersofisticada por dentro; extremadamente sencilla por fuera**.

La v4 sustituye la evolución acumulativa anterior por una arquitectura canónica, transaccional y auditable. Mantiene una única web ejecutiva, pero incorpora por dentro grafo de relaciones, trazabilidad por dato, memoria de investigación, planificación adaptativa, fuente pública estructurada TED, control de calidad y publicación segura.

## Estructura

- `engine/`: dominio, enriquecimiento, grafo, gaps, métricas, calidad y publicación.
- `engine/research/`: planificación, seguridad de red, descubrimiento, extracción, aprendizaje y fuentes estructuradas.
- `config/current/`: política y curación vigentes; no hay cadenas runtime por versión.
- `data/current/`: verdad interna y estado acumulativo; nunca se publica en Pages.
- `data/public/`: proyección mínima que consume el navegador por carga diferida.
- `assets/app/`: un único frontend ejecutivo.

## Garantías v4
- Typed Provenance: fuentes web, documentos Westcon y procedencia histórica se distinguen sin destruir conocimiento.
- Knowledge Guard: Tendencias, Arquitecturas y capacidades no relacionales de fabricantes no pueden desaparecer silenciosamente.

- Una relación visible tiene evidencia del elemento concreto; nunca hereda las fuentes de sus vecinos.
- Un HTTP 200 solo significa transporte correcto: el éxito se mide en evidencia aceptada, datos enriquecidos, entidades nuevas y gaps cerrados.
- Escrituras atómicas, lock interproceso, checkpoints, backoff, circuit breaker y watchdog con terminación controlada.
- Rechazo de SSRF, redirecciones a red privada, respuestas sin límite y URLs con credenciales o puertos no web.
- Investigación diaria, profunda semanal y exhaustiva mensual mediante un único workflow endurecido y sin ejecuciones concurrentes.
- La cabecera de las tablas y la columna Entidad permanecen fijas durante el desplazamiento.

## Validación local

```powershell
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_workflows.py
python scripts/validate.py
python scripts/security_audit.py
node --check assets/app/intelligence.js
node tests/ui_smoke.js
```

## Research manual

```powershell
python scripts/research_supervisor.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts/research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

Los workflows solo publican un snapshot que haya superado todas las puertas de calidad. Una fuente caída queda aislada y la investigación continúa con su siguiente ruta.

Consulta [Arquitectura](docs/ARCHITECTURE.md), [Operación](docs/OPERATIONS.md) y [Auditoría de la v4](docs/RELEASE_V4.md).
