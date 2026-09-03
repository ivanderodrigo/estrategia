# Westcon Iberia Decision Intelligence — v4.2.1

Plataforma de inteligencia de negocio para el canal IT de España y Portugal. Su principio de diseño es: **hipersofisticada por dentro; extremadamente sencilla por fuera**.

La v4 sustituye la evolución acumulativa anterior por una arquitectura canónica, transaccional y auditable. Mantiene una única web ejecutiva, pero incorpora por dentro grafo de relaciones, trazabilidad por dato, memoria de investigación, planificación adaptativa, fuente pública estructurada TED, control de calidad y publicación segura.

## Estructura

- `engine/`: dominio, enriquecimiento, grafo, gaps, métricas, calidad y publicación.
- `engine/research/`: planificación, seguridad de red, descubrimiento, extracción, aprendizaje y fuentes estructuradas.
- `config/current/`: política y curación vigentes; no hay cadenas runtime por versión.
- `data/current/`: verdad interna y estado acumulativo; nunca se publica en Pages.
- `data/public/`: proyección mínima que consume el navegador por carga diferida.
- `assets/app/`: un único frontend ejecutivo.

## Garantías v4.2
- Public Evidence Contract: solo evidencia pública actual y acreditativa sustenta hechos externos visibles; PPT, portfolio e histórico permanecen como memoria interna de investigación.
- Knowledge Guard: Tendencias, Arquitecturas y capacidades no relacionales de fabricantes no pueden desaparecer silenciosamente.
- Preservation Gate: entidades, valores poblados, soporte público, relaciones y research seeds se comparan semánticamente antes/después de cada build.
- Fuentes simples para el usuario: solo evidencia pública actual acredita una celda; documentación interna, PPT, portfolio y linaje histórico nunca aparecen como prueba pública.
- Esquema BI aditivo, columnas vacías ocultas, selector profesional y filtros dinámicos tipados con AND/OR.
- Informes del subconjunto exacto en PDF/imprimible, CSV para Excel y PowerPoint.

- Una relación visible tiene evidencia del elemento concreto; nunca hereda las fuentes de sus vecinos.
- Un HTTP 200 solo significa transporte correcto: el éxito se mide en evidencia aceptada, datos enriquecidos, entidades nuevas y gaps cerrados.
- Escrituras atómicas, lock interproceso, checkpoints, backoff, circuit breaker y watchdog con terminación controlada.
- Rechazo de SSRF, redirecciones a red privada, respuestas sin límite y URLs con credenciales o puertos no web.
- Investigación diaria, profunda semanal y exhaustiva mensual mediante un único workflow endurecido y sin ejecuciones concurrentes.
- La cabecera de las tablas y la columna Entidad permanecen fijas durante el desplazamiento.
- El dataset interno canónico está particionado en shards JSON acotados; `data/current/intelligence.json` es un puntero de compatibilidad y no vuelve a crecer como monolito.
- Los gaps se priorizan P0–P3 por valor de negocio × investigabilidad, con playbook de fuentes por campo y fairness entre secciones.
- `business_weighted_coverage_pct` complementa el número bruto de gaps para medir cobertura útil de inteligencia.

## Validación local

```powershell
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_workflows.py
python -m scripts.legacy_validate_bridge_hf11
python scripts/security_audit.py
node --check assets/app/intelligence.js
node tests/ui_smoke.js
node tests/filter_builder_v410.js
python scripts/audit_release_v410.py
```

## Research manual

```powershell
python scripts/research_supervisor.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts/research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

Los workflows solo publican un snapshot que haya superado todas las puertas de calidad. Una fuente caída queda aislada y la investigación continúa con su siguiente ruta.

Consulta [Arquitectura](docs/ARCHITECTURE.md), [Operación](docs/OPERATIONS.md), [Release v4.2](docs/RELEASE_V4_2.md) e [Instalación v4.2](docs/INSTALL_V420.md).


### v4.2.1 — oportunidad pública contextual

La prioridad de clientes públicos ya no depende solo del tipo de campo. El motor incorpora contexto observable del expediente (importe, estado, hito temporal, necesidad, tecnología y actores identificados), enruta esos huecos a contratación pública y mantiene separados expedientes distintos de un mismo organismo mediante `entity_id`. No se reserva una cuota artificial de P0/P1.

La documentación Westcon/histórica sigue siendo únicamente memoria de investigación; la acreditación externa exige fuente pública actual.
