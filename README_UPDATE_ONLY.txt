UPDATE ONLY v3.10.0

1) Copia el contenido de este ZIP sobre tu carpeta `estrategia` SIN borrar `.git`.

2) Ejecuta:
   $env:PYTHONPATH="scripts"
   python scripts/v310/build_intelligence.py
   python -m unittest tests/test_v310.py
   python scripts/v310/validate_v310.py
   node --check assets/v310/intelligence.js
   node tests/ui_smoke_v310.js

3) Revisa `git status`, commit y push.

4) Para que los cambios generados por cron se reflejen de forma fiable en GitHub Pages:
   Settings > Pages > Build and deployment > Source > GitHub Actions
   y ejecuta una vez el workflow "Publicar Business Intelligence en GitHub Pages".

5) Opcional, documentación interna en repositorio privado:
   PRIVATE_INPUT_REPO=owner/repo-privado
   PRIVATE_INPUT_REPO_TOKEN=token con lectura de ese repo

IMPORTANTE: no guardes documentos confidenciales dentro de `inputs/documents/` si el repositorio principal es público.
