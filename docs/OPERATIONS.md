# Operación

## Requisitos

- Python 3.12 o posterior.
- Node.js 22 para la validación del frontend.
- Git y GitHub Actions para publicación programada.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_workflows.py
python scripts/security_audit.py
python scripts/validate.py
node --check assets/app/intelligence.js
node tests/ui_smoke.js
node tests/filter_builder_v410.js
python scripts/audit_release_v410.py
```

## Calendario automático

| Ciclo | Perfil | Horario UTC | Presupuesto |
|---|---|---:|---:|
| Diario | `daily` | 05:17, todos los días | 12 min |
| Semanal | `deep` | domingo 04:29 | 30 min + fallback |
| Mensual | `exhaustive` | día 1, 03:41 | 55 min + fallback |

Los tres jobs llaman a `.github/workflows/research-run.yml`. La programación entra en funcionamiento cuando el repositorio está en GitHub, Actions está habilitado y la rama por defecto contiene estos workflows.

## Ejecución manual

```powershell
python scripts/research_supervisor.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts/research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

El supervisor reserva tiempo para el build aunque el crawler agote su presupuesto. Siempre reconstruye el grafo, recalcula gaps, ejecuta el auditor y escribe diagnóstico. Solo el publisher de CI realiza commit y push.

## Configuración

`config/current/research_policy.json` es el contrato operativo: perfiles, límites de red, rutas, retención, fuentes estructuradas y política de procedencia. Cambiarlo exige ejecutar toda la validación.

## Fallos y recuperación

- Fuente caída: se registra por dominio, se aplica backoff y continúa la cascada.
- Proceso bloqueado: el watchdog termina el grupo de procesos y conserva el último checkpoint válido.
- Build inválido: el quality gate impide publicar.
- Pérdida de conocimiento: el preservation gate falla y no escribe el snapshot.
- Rama remota avanzada: el publisher aborta para no sobreescribir datos nuevos; el siguiente ciclo parte del estado actualizado.
- Escritura interrumpida: la transacción restaura los ficheros previos.

Los diagnósticos de CI se suben como artefacto durante 14 días incluso si el job falla. `data/current/run_history.json` conserva un historial acotado y `research_state.json` mantiene el aprendizaje entre ciclos.
