# Westcon Iberia Decision Intelligence v3.17.0

Versión de estabilización de la investigación automática diaria, semanal y mensual.

## Cambios clave

- Publicación transaccional ligada dinámicamente a la versión activa; desaparecen referencias fijas a validadores antiguos.
- Configuración compatible para todas las capas heredadas del supervisor.
- Investigación ampliada a 48 rutas por gap, con reanudación, corroboración, contradicción y revalidación.
- Mayoristas e integradores separan fabricantes coincidentes con Westcon de otros fabricantes con posible competencia.
- Las coincidencias son hechos trazables; la relevancia competitiva se mantiene como interpretación amarilla.
- El actualizador parte de v3.16.0, conserva `.git`, valida y revierte ante cualquier error.

## Validación local

```bash
python -m unittest tests/test_v317.py -v
python scripts/v317/validate_v317.py
python tests/test_update_automation_v317.py
node --check assets/v317/intelligence.js
node tests/ui_smoke_v317.js
```

## Ejecuciones

```bash
python scripts/research_supervisor_v317.py --profile daily --max-runtime 720
python scripts/research_supervisor_v317.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor_v317.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```
