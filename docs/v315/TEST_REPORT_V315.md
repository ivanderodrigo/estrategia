# Informe de pruebas v3.15

Fecha: 30 de agosto de 2026.

| Comprobación | Resultado |
|---|---|
| Compilación Python v315 y supervisor | PASS |
| `python -m unittest tests/test_v315.py -v` | PASS, 37 pruebas |
| `python scripts/v315/validate_v315.py` | PASS |
| `node --check assets/v315/intelligence.js` | PASS |
| `node tests/ui_smoke_v315.js` | PASS |
| Reconstrucción `daily --skip-v33` | PASS |
| Instalación update-only sobre copia v3.14 con `.git` | PASS, 39 archivos |
| Rollback forzado por test fallido | PASS, VERSION, `index.html` y `.git/HEAD` restaurados |

Las pruebas cubren versión, mínimos de entidades, Comstor, separación fabricante/mayorista, visibilidad de columnas, placeholders, 15 pases, cierre de gaps, resiliencia, fuentes, métricas, señales e interpretaciones, trazabilidad fuerte, clasificación de fuentes secundarias, confianza, encabezados, exportación, workflows, Pages y responsive.
