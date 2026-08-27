# Resultados de pruebas v3.4.0

Fecha: 2026-08-27

## Baseline v3.3.3a

| Suite | Resultado |
| --- | --- |
| Unit tests | 106 ejecutados; 104 PASS; 2 FAIL |
| UI smoke | FAIL por KPI/gate rígido |
| Selftest, resiliencia, schedule y validator | PASS |

Fallos reproducidos y corregidos en v3.4:

1. expectativa obsoleta de v3.2.5 cuando la capa ya era v3.2.6;
2. validador de provenance que no cubría una forma legacy;
3. smoke UI acoplado a un total fijo y al gate absoluto.

## Production Candidate v3.4.0

| Comando | Resultado esperado y obtenido |
| --- | --- |
| `python -m unittest discover -s tests -p "test*.py" -v` | 127/127 PASS |
| `node --check assets/app.js` | PASS |
| `node --check assets/v340/business-intelligence.js` | PASS |
| `node scripts/ui_smoke.js` | PASS |
| `node tests/ui_smoke_v340.js` | PASS |
| `python tools/validar_v340.py` | VALIDACIÓN v3.4.0 PASS |
| `python tools/auditar_v340.py` | PASS; 1 warning; 0 errores |
| `python tools/aplicar_v340.py` | PASS e idempotente |
| migración desde copia v3.3.3a | PASS |
| daily offline | PASS / published |
| weekly offline | PASS / published |
| validación JSON completa | PASS |
| validación estática de workflows | PASS |

El smoke v3.4 verifica 24 recomendaciones, 65 integradores, 14 mayoristas, 12 arquitecturas y 129 fuentes operativas.

## Comandos de reproducción

```bash
python tools/aplicar_v340.py
python tools/validar_v340.py
python tools/auditar_v340.py
python -m unittest discover -s tests -p "test*.py" -v
node scripts/ui_smoke.js
node tests/ui_smoke_v340.js
python scripts/research_supervisor_v34.py --profile daily --max-runtime 180 --skip-v33
python scripts/research_supervisor_v34.py --profile weekly --max-runtime 240 --skip-v33
```

La prueba visual local exacta se documenta en `README_V340.md`. La generación de PDF/PPT necesita conexión a las librerías CDN usadas por la baseline.
