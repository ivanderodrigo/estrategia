# Instalación y validación exacta

## UPDATE_ONLY desde la v3.18.0 instalada

Deja el ZIP UPDATE_ONLY en `C:\Users\ivand\Downloads`, descomprímelo fuera de `estrategia` y ejecuta:

```powershell
cd C:\Users\ivand\Downloads
Expand-Archive -Path ".\westcon-decision-intelligence-v3.19.0-UPDATE_ONLY.zip" -DestinationPath ".\westcon-decision-intelligence-v3.19.0-UPDATE_ONLY" -Force
python ".\westcon-decision-intelligence-v3.19.0-UPDATE_ONLY\install_update_v319.py" "C:\Users\ivand\Downloads\estrategia"
```

El instalador exige `VERSION=3.18.0`, repositorio Git limpio, preserva `.git`, no toca archivos no versionados del usuario, no hace commit ni push y ejecuta rollback si falla.

## Validación posterior

```powershell
cd C:\Users\ivand\Downloads\estrategia
Get-Content VERSION
python -m unittest discover -s tests -p "test_*.py" -v
python scripts\validate.py
node --check assets\app\intelligence.js
node tests\ui_smoke_v319.js
git status
```

`Get-Content VERSION` debe devolver `3.19.0`.

## Investigación

```powershell
python scripts\research_supervisor.py --profile daily --max-runtime 720 --fallback-runtime 0
python scripts\research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
python scripts\research_supervisor.py --profile exhaustive --max-runtime 3300 --fallback-runtime 300
```

## Git

```powershell
git add -A
git status
git commit -m "Upgrade Westcon Decision Intelligence to v3.19.0 Production Candidate"
git pull --rebase origin main
git push origin main
git status
```
