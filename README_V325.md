# Westcon Iberia Decision Intelligence v3.2.5

Hotfix de compatibilidad Windows para la fase legacy y observabilidad de la foundation.

## Corrige
- `selectors/select()` sobre pipes de subprocess en Windows (`WinError 10093`).
- Sustituye el streaming legacy por un lector `thread + queue`, portable en Windows/Linux/macOS.
- Mantiene streaming, heartbeat, timeout, log y terminación del proceso.
- v3.1 muestra explícitamente `legacy ok/failed/skipped`.
- v3.2 muestra `foundation v31=... legacy=...` en la línea final.
- La instalación crea backup del `scripts/research_supervisor.py` original antes de tocarlo.

## Instalación
Copiar el contenido encima del repositorio, reemplazar coincidentes y ejecutar:

```powershell
python tools/aplicar_v325.py
Get-Content VERSION
python tests/test_v325_unittest.py
```

Después realizar una prueba legacy corta y, si termina, la integral:

```powershell
python scripts/research_supervisor.py --profile daily --max-runtime 60
python scripts/research_supervisor_v32.py --profile daily --max-runtime 720
```
