# Changelog v3.16.0

## Investigación y datos

- Incorporadas 21 nuevas rutas primarias específicas, además del catálogo de 360 fuentes heredado de v3.15.
- Más de 500 valores añadidos y más de 350 campos antes vacíos cubiertos con evidencia directa o derivación conservadora etiquetada.
- Investigación oficial ampliada para 12 grandes cuentas, cinco mayoristas y cuatro integradores; las fuentes conservan URL, fecha, descripción, alcance y tipo.
- Normalizada la trazabilidad histórica y explicitado cuándo una fecha no fue publicada.

## Motor

- Cada gap genera 32 pases —incluida corroboración independiente y búsqueda de contradicciones— y permanece abierto si una búsqueda no devuelve resultados.
- Añadidas colas reanudables, checkpoints, reintentos, backoff exponencial, circuit breaker, límites por dominio y aprendizaje por estrategia.
- Añadidos informes reproducibles de métricas, gaps, fuentes y cobertura.

## Interfaz

- Sustituida la representación ambigua de ausencia por `Por investigar`.
- Eliminada la ocultación de columnas por baja densidad.
- Separadas confianza del hecho, confianza de la interpretación y riesgo de acción.
- Añadido semáforo vinculante: señales siempre rojas; interpretaciones amarillas; verde reservado a hechos con evidencia oficial o fuerte corroboración.
- Revisados encabezados para explicar contenido y utilidad.

## Calidad

- Nuevas pruebas v3.16 para roles, Comstor, placeholders, evidencia fuerte, fuentes secundarias, señales, cierre de gaps, encabezados, workflows y Pages.
- Instalador update-only transaccional con rollback y conservación de `.git`.
