# Changelog — v3.4.0 Production Candidate

Fecha: 2026-08-27

## Added

- Motor v3.4 de recomendaciones con confianza factual, confianza interpretativa y riesgo de acción separados.
- Tipos ACTUAR, PREPARAR / VALIDAR, INVESTIGAR, VIGILAR y disposición DESCARTAR / NO MOSTRAR.
- Auditoría obligatoria `data/v34/recommendation_audit.json`.
- Quality report, source coverage, catálogo de fuentes, business intelligence report, histórico, research queue y métricas antes/después.
- Executive Decision Brief nuevo.
- Tablas v3.4 para integradores/mayoristas con orden, selección, movimiento, persistencia, filtros, búsqueda, CSV y auto-ocultado por cobertura.
- Inteligencia de movimiento del ecosistema: fabricantes confirmados/probables, perfiles buscados y señales de contratación.
- Playbook de fuente Integrador/Mayorista × Fabricante con partner locator, nivel, certificaciones, casos, premios, marketplace y empleo.
- Catálogo de 129 fuentes operativas públicas/gratuitas y 280 candidatos totales contando registry existente.
- Source learning por entidad × dimensión × país × tipo.
- Investigación adaptativa con fuente y query recomendadas por gap.
- 12 arquitecturas originales con problema, oportunidad, capas, vendors, integraciones, integradores, gaps, servicios, monetización, recurrencia, KPIs, riesgos y readiness.
- Histórico 30/90/365.
- PDF ejecutivo y PowerPoint narrativo v3.4.
- Instalador/migrador seguro `tools/aplicar_v340.py`, validador y auditor.
- 21 pruebas v3.4 adicionales y smoke UI específico; total 127 tests.

## Changed

- Reemplazado el gate absoluto 100/100 por acción proporcional a evidencia y riesgo.
- Separados estado, intensidad y confianza de relaciones.
- Deduplificada evidencia por URL o título/fuente/fecha.
- Partner locators y casos oficiales reciben tratamiento explícito y distinto.
- La ausencia de evidencia nunca se interpreta como relación inexistente.
- Fabricantes mal clasificados se excluyen de integradores v3.4 sin borrar la evidencia heredada.
- Columnas internas dejan de mostrarse al usuario.
- Columnas con cobertura inferior al 20 % se ocultan automáticamente.
- `deep` y `exhaustive` son aliases compatibles de weekly/monthly.
- UI smoke deja de depender de un KPI numérico fijo.
- Source success rate queda limitado a 0–1.

## Fixed

- Test legacy v3.2.6 con expectativa de versión obsoleta.
- Validador v3.3 de provenance para filas legacy.
- Duplicación de evidencia en matrices de relación.
- Cuatro conflictos fabricante/integrador: Cisco, Fortinet, Infoblox y Arista Networks.
- Falsos positivos heredados de hiring sin lenguaje explícito.
- Mensajes y exportaciones que seguían presentando acciones como bloqueadas bajo 100/100.

## Known issues

- Siete evidencias antiguas permanecen como warning contextual.
- 78 perfiles están por debajo del 50 % del esquema ampliado.
- Parte de la evidencia heredada usa redirect de Google News.
- PDF/PPT requieren CDN accesible desde el navegador.
- No hay datos internos financieros; economics son relativos.
- La revisión visual automatizada en el navegador cloud no pudo acceder a localhost; smoke runtime, DOM/JSON y sintaxis sí pasan.

## Validation

- Unit/regression: 127/127 PASS.
- JavaScript syntax: PASS.
- UI smoke legacy y v3.4: PASS.
- Migration v3.3.3a → v3.4: PASS.
- Daily offline: PASS/published.
- Weekly offline: PASS/published.
- Recommendation audit: PASS, 0 errores.
- Quality audit: PASS, 0 errores, 1 warning documentado.

