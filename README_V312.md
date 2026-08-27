# Westcon Iberia Decision Intelligence v3.1.2 hotfix

La v3.1.2 corrige el diagnóstico observado en v3.1.1: llamadas HTTP válidas a Google News RSS pero cero señales aceptadas.

Cambios principales:

- queries compactas con alternativas OR por dimensión, evitando cadenas de palabras que se comportan como un AND excesivamente restrictivo;
- aliases conservadores de entidades (por ejemplo `NTT DATA Spain` -> `NTT DATA`, `V-Valley / Esprinet` -> ambas marcas);
- fair-share real: una primera dimensión por entidad antes de volver sobre la misma entidad;
- Google News y GDELT se intercalan desde el primer lote, por lo que una ejecución corta ya prueba ambos transportes;
- concurrencia acotada (4 workers en daily) para aumentar cobertura sin inundar endpoints gratuitos;
- diagnóstico por proveedor: llamadas, filas raw, aceptadas, rechazadas por relevancia, duplicados y latencia;
- preservación de señales previas y publicación `degraded` si una ejecución no aporta inteligencia nueva;
- deuda sigue siendo por gap entidad x dimensión. Con el seed actual, 463 es el universo completo de gaps, no un error cartesiano.

## Instalación

Copiar el contenido del hotfix encima del repositorio, reemplazando archivos coincidentes. No borrar `.git`, `.venv` ni `data`.

El instalador v3.1.2 es idempotente: si al copiar el ZIP el propio hotfix ya está en destino, no intenta copiar un archivo sobre sí mismo.

```powershell
python tools/aplicar_v312.py
python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy
```

La línea final incluirá, por proveedor, `raw`, `accepted` y `rejected`. Esto permite distinguir inmediatamente entre: proveedor sin resultados, consultas demasiado restrictivas, filtro de relevancia demasiado estricto o duplicación.
