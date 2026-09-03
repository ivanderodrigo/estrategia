# Westcon Iberia Decision Intelligence v4.1.0

## Resultado

Evolución mayor, aditiva y compatible con la base estable `4.0.6 / 44abf7d`. No se reconstruye el producto, no se cambia su topología canónica `data/current → data/public` y no se elimina conocimiento por falta de fuente moderna.

## Fuentes y trazabilidad

- La UI normal solo publica dos familias acreditativas: documentación oficial Westcon aportada y evidencia pública actual trazable.
- Histórico, archivo recuperado, corroboración de informes y linaje siguen íntegros en la verdad interna, pero no aparecen mezclados con las fuentes finales.
- `Portfolio Westcon` y `Presentación Westcon` se unifican por identidad de documento; la slide y el dato atómico permanecen.
- Un claim puede conservar a la vez fuente documental Westcon y fuente pública.
- `source_binding=discovery-only` y `discovery-candidate` no pueden cerrar un gap ni salir como evidencia acreditativa.
- Los claims H sin soporte final reciben prioridad específica en el research planner.

## Inteligencia de negocio

El esquema de Fabricantes, Integradores, Mayoristas y Clientes se amplía de forma aditiva con tipos explícitos: texto, lista, número, fecha, boolean y confianza. Las nuevas dimensiones vacías se ocultan en la tabla, pero quedan declaradas como deuda de investigación; no se inventan valores.

La confianza se recalcula por fuerza de la mejor fuente relevante, primariedad, actualidad, corroboración independiente y contradicciones. La UI explica evidencias relevantes, calidad, vigencia y qué falta para mejorar el nivel; no suma URLs de forma ingenua.

## Tablas y análisis

- Selector de columnas de alto contraste con búsqueda, seleccionar todas, restablecer, esenciales bloqueadas, scroll y persistencia.
- Columnas por defecto, ocultación de columnas totalmente vacías, ordenación, drag/reorder y resize.
- Panel plegable `Analizar estos datos` debajo de cada tabla.
- Reglas AND/OR y grupos, operadores tipados, contador inmediato, persistencia de sesión, filtros guardados y estado de URL.
- Informes construidos exactamente con el subconjunto filtrado: vista imprimible/PDF, CSV para Excel y PowerPoint.
- El informe incluye criterios, fecha, número de entidades, resumen descriptivo derivado, tabla, fuentes, confianza y advertencias de investigación.

## Investigación

Se amplía la cascada gratuita/pública para partner locators, directorios, certificaciones, casos, marketplaces, annual reports, IR, careers, contratación ES/PT/TED, servicios, formación, financiación, logística, analistas y prensa de canal. Discovery y evidencia acreditativa permanecen separadas.

## Gate de conocimiento

Cada build compara entrada y salida y falla si pierde entidades, valores poblados, evidencias válidas, relaciones o capacidades Westcon documentadas. Mantiene además mínimos explícitos para fabricantes, tendencias y arquitecturas.

Resultado de esta entrega: `PASS`, con 0 pérdidas sobre 13.235 valores, 2.319 fingerprints de evidencia válida, 1.353 relaciones y 109 capacidades Westcon documentadas.

## Tests

- 76 tests Python: `PASS`.
- Smoke UI v4.1.0: `PASS`.
- Filter builder + informe de subconjunto exacto: `PASS`.
- Workflows, validación canónica, seguridad, sintaxis JS y compileall: `PASS`.
- Se intentó además una inspección visual en navegador cloud; ese navegador bloquea URLs localhost. Por ello la entrega no declara una captura visual manual y conserva como evidencia el smoke responsive/DOM/CSS automatizado.

Las métricas completas están en `docs/METRICS_V410.json`.
