# Informe de pruebas v3.17

Fecha de validación final: 31 de agosto de 2026.

| Comprobación | Resultado |
|---|---|
| Compilación Python v317 y supervisor | PASS |
| `python -m unittest tests/test_v317.py -v` | PASS, 43 pruebas |
| `python tests/test_update_automation_v317.py` | PASS, publicador dinámico y validador vigente |
| `python scripts/v317/validate_v317.py` | PASS |
| `node --check assets/v317/intelligence.js` | PASS |
| `node tests/ui_smoke_v317.js` | PASS |
| Reconstrucción `daily --skip-v33` | PASS |
| Instalación update-only sobre copia v3.15 con `.git` | PASS, 38 archivos |
| Preservación de `.git/HEAD` y ausencia de commit/push | PASS |

Las pruebas cubren versión, mínimos de entidades, Comstor, separación fabricante/mayorista, visibilidad de columnas, placeholders, 32 pases, contradicciones, cierre de gaps, resiliencia, fuentes, métricas, señales rojas, interpretaciones amarillas, trazabilidad fuerte, clasificación de fuentes secundarias, confianza, encabezados, exportación, workflows, Pages y responsive.
