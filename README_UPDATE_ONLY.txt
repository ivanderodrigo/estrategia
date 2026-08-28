WESTCON IBERIA BUSINESS INTELLIGENCE v3.7.0 - UPDATE ONLY

Instalación recomendada sobre v3.6.1/v3.7 previa:
1. NO borres el repositorio y NO borres .git.
2. Copia todo el contenido de este paquete sobre la raíz del repositorio.
3. Acepta reemplazar archivos existentes.
4. Este paquete NO incluye data/v34, para preservar los datasets dinámicos/históricos del repositorio.
5. Valida:
   python -m unittest tests/test_v370.py
   python scripts/v37/validate_v37.py
   node --check assets/v370/intelligence.js
   node tests/ui_smoke_v370.js
6. Después: git add -A, commit, git pull --rebase origin main, git push origin main.

La actualización automática v3.7 usa research_gaps.json para priorizar huecos, datos de baja confianza y evidencias envejecidas.
