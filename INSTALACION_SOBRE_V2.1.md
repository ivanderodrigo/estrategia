# Instalación de v3.0 sobre Westcon Iberia Decision Intelligence v2.1

Esta actualización sustituye el motor de investigación, los workflows, el frontend y las exportaciones. El histórico y el aprendizaje de v2.1 pueden conservarse. No requiere claves de búsqueda ni suscripciones.

## 1. Hacer una copia recuperable

Desde la raíz del repositorio v2.1:

```bash
git status
git add -A
git commit -m "backup antes de actualizar a v3.0"
git tag backup-v2.1-pre-v3
```

Si no utiliza Git, comprima la carpeta v2.1 completa antes de continuar. No prosiga si `git status` muestra cambios que no quiere incluir en la copia.

## 2. Descomprimir v3.0 fuera de la carpeta anterior

```text
proyectos/
├── westcon-v2.1/
└── westcon-v3.0/
```

No descomprima directamente encima hasta haber guardado los datos dinámicos.

## 3. Conservar aprendizaje e histórico de v2.1

Copie a una carpeta temporal, si existen:

- `data/history/`
- `data/research_learning.json`
- `data/research.latest.json`, solo como referencia o último dato conocido
- cualquier archivo propio no incluido en la distribución

No reutilice automáticamente `data/research_queue.json`: v3 incluye un checkpoint nuevo y reanudable. Conserve el antiguo únicamente para auditoría.

Linux/macOS:

```bash
mkdir -p ../westcon-v21-preserved
cp -R data/history ../westcon-v21-preserved/ 2>/dev/null || true
cp data/research_learning.json ../westcon-v21-preserved/ 2>/dev/null || true
cp data/research.latest.json ../westcon-v21-preserved/ 2>/dev/null || true
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force ..\westcon-v21-preserved
Copy-Item data\history ..\westcon-v21-preserved\history -Recurse -ErrorAction SilentlyContinue
Copy-Item data\research_learning.json ..\westcon-v21-preserved\ -ErrorAction SilentlyContinue
Copy-Item data\research.latest.json ..\westcon-v21-preserved\ -ErrorAction SilentlyContinue
```

## 4. Sustituir la aplicación por v3.0

Copie desde el ZIP v3.0 a la raíz del repositorio anterior:

- `.github/workflows/`, `assets/`, `config/`, `data/` y `scripts/`
- `index.html`, `README.md`, `requirements.txt`
- `INSTALACION_SOBRE_V2.1.md` y `CHANGELOG_v3.0.md`

Después, restaure dentro de v3.0 el contenido histórico guardado:

```bash
cp -R ../westcon-v21-preserved/history/* data/history/ 2>/dev/null || true
```

Para `research_learning.json`, empiece preferentemente con el archivo entregado por v3. Si desea conservar el aprendizaje anterior, valide primero que su estructura contenga `version`, `strategies` y `sources`; haga una copia y ejecute todas las pruebas. La aplicación puede reaprender de forma segura si decide no migrarlo.

## 5. Eliminar secretos ya innecesarios

La v3.0 no lee claves de búsqueda. Puede retirar del repositorio GitHub, si existían, `BRAVE_SEARCH_API_KEY` y `BASE_API_TOKEN` desde **Settings → Secrets and variables → Actions**. La retirada no afecta a v3.0.

## 6. Crear el entorno y validar la migración

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m py_compile scripts/*.py
python scripts/selftest.py
python scripts/test_resilience.py
python scripts/test_schedule.py
python scripts/validate.py
node --check assets/app.js
node scripts/ui_smoke.js
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m py_compile scripts/*.py
python scripts/selftest.py
python scripts/test_resilience.py
python scripts/test_schedule.py
python scripts/validate.py
node --check assets/app.js
node scripts/ui_smoke.js
```

Todos los comandos deben finalizar con `OK`. No publique si `validate.py` muestra `ERROR`.

## 7. Configurar la actualización automática

Madrid:

```bash
python scripts/configure_updates.py \
  --timezone Europe/Madrid \
  --daily 06:23 \
  --weekly SUN@04:47 \
  --monthly 1@03:17
```

Lisboa:

```bash
python scripts/configure_updates.py --timezone Europe/Lisbon
```

Compruebe el resultado:

```bash
python scripts/configure_updates.py --show
python scripts/test_schedule.py
```

El script reescribe solo los bloques `CONFIGURABLE_SCHEDULE` y mantiene la ejecución manual. No añada el antiguo comando duplicado `research.py ... || research.py ...`.

## 8. Probar localmente

```bash
python -m http.server 8000
```

Abra `http://localhost:8000` y compruebe:

- que el menú se colapsa en pantallas estrechas;
- que las vistas de fabricantes, mayoristas e integradores filtran correctamente;
- que las columnas se pueden seleccionar, ordenar y mover;
- que los tooltips muestran fuente y confianza;
- que **Operación** muestra run ID, etapas, salud y fallos;
- que PDF y PowerPoint incluyen los campos elegidos y no exportan acciones por debajo de 100/100.

## 9. Primera actualización controlada

```bash
python scripts/research_supervisor.py --profile daily --max-runtime 720
python scripts/validate.py
```

Resultado esperado:

- `complete` o `partial-recoverable`;
- nunca pérdida del dataset anterior;
- `data/run_manifest.latest.json` con todas las etapas;
- fallos de fuentes individuales en `data/research_errors.json` sin abortar el conjunto;
- pendientes en `data/research_queue.json` si se agotó el presupuesto.

Después puede ejecutar:

```bash
python scripts/research_supervisor.py --profile deep --max-runtime 1800 --fallback-runtime 240
```

## 10. Publicar

```bash
git status
git add -A
git commit -m "upgrade: Westcon Iberia Decision Intelligence v3.0"
git push origin main
```

En GitHub, abra **Actions** y lance **Inteligencia pública diaria** mediante `workflow_dispatch`. Cuando termine:

1. confirme que validación y commit han finalizado;
2. descargue el artefacto `research-diagnostic-daily-*`;
3. abra la web publicada y revise **Operación**;
4. lance el workflow semanal.

## Rollback

```bash
git switch -c rollback-v21 backup-v2.1-pre-v3
```

Esto crea una rama recuperable con el estado anterior. No use `reset --hard` si existen cambios sin copiar.

## Si una actualización falla

Use el `runId` visible en **Operación** y revise, en este orden:

1. `data/supervisor.latest.json`;
2. `data/run_manifest.latest.json`;
3. `data/research_errors.json`;
4. `data/source_health.json`;
5. el artefacto `research-diagnostic-*` de GitHub Actions.

La combinación `stage + errorType + source + runId` permite localizar qué modificar sin perder el resto de la ejecución. El supervisor conservará o restaurará el último dataset validado.
