# Auditoría de calidad v3.4.0

Fecha de cierre: 2026-08-27  
Versión auditada: 3.4.0 Production Candidate

## Resultado

**PASS con un warning conocido y sin errores bloqueantes.**

La auditoría ejecutable es `python tools/auditar_v340.py`. Sus resultados estructurados están en `data/v34/quality_report.json` y `data/v34/recommendation_audit.json`.

## Gates revisados

| Gate | Resultado | Evidencia de control |
| --- | --- | --- |
| Identidad y roles | PASS | Cuatro fabricantes mal clasificados como integradores fueron excluidos |
| Duplicados | PASS | 80 repeticiones heredadas reducidas a 0 en relaciones v3.4 |
| Geografía | PASS | País/alcance separado de estado y confianza |
| Provenance | PASS | URL, fecha, tipo, calidad, confianza e IDs de evidencia |
| Recomendaciones | PASS | 24 publicadas; 0 sin evidencia; 0 demasiado fuertes |
| Relaciones | PASS | Estado e intensidad independientes; ausencia no implica inexistencia |
| Fuentes | PASS | 129 fuentes operativas; aprendizaje por entidad/dimensión/país/tipo |
| Empleo/talento | PASS | 5 señales aceptadas; 1 falso positivo rechazado |
| Cobertura | PASS | Deuda visible; no se infla la calidad por rellenar campos sin soporte |
| Columnas | PASS | Campos internos fuera de UI; auto-ocultación por debajo del 20 % |
| JavaScript | PASS | Sintaxis y smoke tests |
| Frontend | PASS técnico | Contratos DOM/JSON y runtime estático |
| Enlaces/fuentes | PASS con deuda | Redirects de agregador marcados para resolver |
| Windows | PASS estático | Paths, comandos y workflows revisados; instalador usa `pathlib` |
| GitHub Actions/Pages | PASS estático | Perfiles y outputs v3.4 incluidos |
| Informes | PASS técnico | Exportadores ejecutivos separados del dashboard |
| Outputs obligatorios | PASS | Los cuatro JSON exigidos y datasets auxiliares están presentes |

## Auditoría de recomendaciones

| Control | Resultado |
| --- | ---: |
| Candidatas evaluadas | 31 |
| Publicadas | 24 |
| Descartadas con motivo | 7 |
| Inventadas | 0 |
| Sin evidencia | 0 |
| Ausencia injustificada | 0 |
| Exceso | 0 |
| Genéricas | 0 |
| Duplicadas | 0 |
| Contradictorias | 0 |
| Sin acción explícita | 0 |
| Demasiado fuertes para la evidencia | 0 |

Distribución publicada: 18 PREPARAR / VALIDAR, 3 INVESTIGAR, 3 VIGILAR y 0 ACTUAR. La ausencia de ACTUAR no es un fallo: evita convertir indicios heredados en mandatos de inversión.

## Warning aceptado

Siete evidencias tienen más de tres años. Se conservan como contexto histórico y pueden contribuir a una hipótesis, pero no bastan por sí solas para confirmar una relación actual ni elevar una recomendación a ACTUAR.

## Revisión visual

La aplicación respondió por HTTP local y superó contratos DOM/JSON, smoke runtime y sintaxis. El navegador de revisión aislado no pudo alcanzar `localhost`; por ello la inspección visual final de PDF/PPT y los breakpoints debe repetirse en el equipo del revisor siguiendo `README_V340.md`, sección 13. Esta limitación no se oculta ni se convierte en un PASS visual ficticio.

## Conclusión

La candidata es defendible para revisión de aceptación: los fallos bloqueantes son cero, las recomendaciones son trazables y proporcionales, y la deuda de conocimiento sigue visible. Antes de promover a producción definitiva debe completarse la revisión visual manual y renovarse la evidencia antigua prioritaria.
