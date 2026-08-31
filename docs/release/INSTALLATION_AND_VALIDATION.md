# Instalación y validación

## UPDATE_ONLY sobre v3.19.0

```powershell
cd C:\Users\ivand\Downloads
Expand-Archive -Path ".\westcon-decision-intelligence-v3.20.0-UPDATE_ONLY.zip" -DestinationPath ".\westcon-decision-intelligence-v3.20.0-UPDATE_ONLY" -Force
python ".\westcon-decision-intelligence-v3.20.0-UPDATE_ONLY\install_update_v320.py" "C:\Users\ivand\Downloads\estrategia"
```

## Validar

```powershell
cd C:\Users\ivand\Downloads\estrategia
Get-Content VERSION
python -m unittest discover -s tests -p "test_*.py" -v
python scripts\validate_workflows.py
python scripts\validate.py
node --check assets\app\intelligence.js
node tests\ui_smoke_v320.js
git status
```

## Git

```powershell
git add -A
git commit -m "Upgrade Westcon Decision Intelligence to v3.20.0 Production Candidate"
git pull --rebase origin main
git push origin main
```
