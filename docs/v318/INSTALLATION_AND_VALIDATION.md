# Instalación, validación y Git — v3.18.0

## UPDATE_ONLY recomendado sobre la baseline adjunta v3.17.0
1. No borres `.git`.
2. Descomprime `westcon-decision-intelligence-v3.18.0-UPDATE_ONLY.zip` fuera de la carpeta `estrategia`.
3. Desde PowerShell, ejecuta:
```powershell
python .\westcon-decision-intelligence-v3.18.0-UPDATE_ONLY\install_update_v318.py C:\ruta\a\estrategia
```
4. El instalador verifica la baseline, copia solo los archivos del manifest, ejecuta validaciones y revierte si falla. No hace commit ni push.

## Validación manual
```powershell
cd C:\ruta\a\estrategia
python -m unittest tests/test_v318.py -v
python tests/test_update_automation_v318.py
python scripts/v318/validate_v318.py
python scripts/v318/audit_workflows.py
python scripts/test_resilience.py
python scripts/test_schedule.py
node --check assets/v318/intelligence.js
node tests/ui_smoke_v318.js
```

## Ejecución local
```powershell
python -m http.server 8000
```
Abrir `http://localhost:8000/`.

## Research
```powershell
python scripts/research_supervisor_v318.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts/research_supervisor_v318.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts/research_supervisor_v318.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

## Git
Primero comprueba:
```powershell
git status
git pull --rebase origin main
```
Si el pull indica cambios locales sin guardar, no fuerces: revisa `git status`, conserva tus cambios y resuelve antes de continuar.

Después de instalar y validar:
```powershell
git add -A
git status
git commit -m "Upgrade Westcon Decision Intelligence to v3.18.0"
git pull --rebase origin main
git push origin main
```
