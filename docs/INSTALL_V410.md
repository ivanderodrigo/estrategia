# Instalación y rollback de v4.1.0 en Windows

## Upgrade sobre el repositorio actual

Coloque `westcon-decision-intelligence-v4.1.0-upgrade.zip` en `C:\Users\ivand\Downloads` y ejecute PowerShell:

```powershell
Set-Location "C:\Users\ivand\Downloads"
Expand-Archive -LiteralPath ".\westcon-decision-intelligence-v4.1.0-upgrade.zip" -DestinationPath ".\westcon-v4.1.0-upgrade" -Force
Set-ExecutionPolicy -Scope Process Bypass
& ".\westcon-v4.1.0-upgrade\INSTALL_UPGRADE.ps1" -Target "C:\Users\ivand\Downloads\estrategia"
```

El instalador:

1. comprueba versión compatible y SHA-256 de cada archivo del payload;
2. crea un backup recuperable dentro de `estrategia\.upgrade-backups`;
3. sustituye código/configuración/frontend, nunca `.git`;
4. ejecuta el pipeline sobre los datos existentes del repositorio destino;
5. bloquea la entrega si desaparece conocimiento;
6. ejecuta tests Python, UI, filtros, workflows, validación y seguridad;
7. hace rollback automático si cualquier paso falla.

Se recomienda no usar `-SkipTests`. Ese switch existe solo para diagnóstico controlado.

## Rollback

Con la carpeta extraída del ZIP todavía disponible:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "C:\Users\ivand\Downloads\westcon-v4.1.0-upgrade\ROLLBACK.ps1" -Target "C:\Users\ivand\Downloads\estrategia"
```

El script lee el último backup v4.1.0. Para elegir uno concreto:

```powershell
& "C:\Users\ivand\Downloads\westcon-v4.1.0-upgrade\ROLLBACK.ps1" `
  -Target "C:\Users\ivand\Downloads\estrategia" `
  -Backup "C:\Users\ivand\Downloads\estrategia\.upgrade-backups\v4.1.0-AAAAMMDD-HHMMSS"
```

## ZIP completo

Para probar una copia independiente sin tocar el repositorio actual:

```powershell
Set-Location "C:\Users\ivand\Downloads"
Expand-Archive -LiteralPath ".\westcon-decision-intelligence-v4.1.0-full.zip" -DestinationPath ".\estrategia-v4.1.0" -Force
Set-Location ".\estrategia-v4.1.0\westcon-decision-intelligence-v4.1.0"
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python -m http.server 8000
```

Abra `http://localhost:8000`. No se realiza commit ni push en ningún paso.
