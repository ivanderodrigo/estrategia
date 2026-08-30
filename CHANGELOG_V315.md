# Changelog v3.15.0

## Investigación y datos

- Incorporadas 66 rutas de fuente públicas en partner directories, mayoristas, clientes, empleo, contratación pública, organismos, analistas, prensa sectorial y archivos web.
- Enriquecidos 21 registros y 44 campos antes vacíos con 124 valores nuevos.
- Añadida investigación documentada para Ciena, NETSCOUT, Ericsson Cradlepoint, Certes Networks y Weblib; seis mayoristas ibéricos; siete grandes cuentas; y empleo de Capgemini, Atos y Telefónica.
- Normalizada la trazabilidad histórica y explicitado cuándo una fecha no fue publicada.

## Motor

- Cada gap genera 15 pases y permanece abierto si una búsqueda no devuelve resultados.
- Añadidas colas reanudables, checkpoints, reintentos, backoff exponencial, circuit breaker, límites por dominio y aprendizaje por estrategia.
- Añadidos informes reproducibles de métricas, gaps, fuentes y cobertura.

## Interfaz

- Sustituida la representación ambigua de ausencia por `Por investigar`.
- Eliminada la ocultación de columnas por baja densidad.
- Separadas confianza del hecho, confianza de la interpretación y riesgo de acción.
- Revisados encabezados para explicar contenido y utilidad.

## Calidad

- Nuevas pruebas v3.15 para roles, Comstor, placeholders, evidencia fuerte, fuentes secundarias, señales, cierre de gaps, encabezados, workflows y Pages.
- Instalador update-only transaccional con rollback y conservación de `.git`.
