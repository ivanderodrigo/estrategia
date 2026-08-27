# Westcon Iberia Decision Intelligence v3.2.6

Hotfix de orquestación y persistencia.

Corrige el validador legacy que exigía literalmente `research_supervisor.py` en los workflows, aunque v3.2 usa `research_supervisor_v32.py`. También garantiza que los workflows daily/weekly/monthly persistan y suban como diagnóstico `data/v31/` y `data/v32/`, y que el preflight compile toda la cadena legacy -> v31 -> v32.

Instalación desde la raíz del repositorio:

```powershell
python tools/aplicar_v326.py
Get-Content VERSION
python tests/test_v326_unittest.py
python scripts/validate.py
python scripts/research_supervisor.py --profile daily --max-runtime 60
```

Si la prueba legacy corta ya no muestra `Workflow sin supervisor/diagnóstico`, ejecutar la prueba integral:

```powershell
python scripts/research_supervisor_v32.py --profile daily --max-runtime 720
```
