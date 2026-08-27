# Westcon Iberia Decision Intelligence v3.3.3a

Microfix de estabilización geográfica previo a la baseline v3.4.

- Un país explícito en el nombre de la entidad (Spain/España/Portugal) prevalece sobre ámbitos ES/PT contradictorios inferidos de fuentes.
- Las variantes contradictorias no se borran: quedan preservadas en `operations` y en `deduplication_report.json`.
- El informe distingue conflictos detectados, resueltos y no resueltos.
- La validación falla si queda algún conflicto nombre-ámbito sin resolver.

Instalación tras descomprimir sobre el repositorio:

```powershell
python tools/aplicar_v333a.py
python tests/test_v333a_unittest.py
python tests/test_v333_unittest.py
python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32
```

La salida debe mostrar `scope conflicts 1 resolved/0 unresolved` para el dataset actual y `errors 0`.
