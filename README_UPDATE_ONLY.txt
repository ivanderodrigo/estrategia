UPDATE ONLY v3.13.0

IMPORTANTE: si la v3.12 está staged pero todavía no se ha hecho commit, NO hagas un commit intermedio.
La v3.13 puede instalarse directamente encima y terminar en un único commit v3.13.

1. Copia el contenido del ZIP encima del repositorio actual SIN borrar .git.

2. Limpia los artefactos activos de v3.12:

   powershell -ExecutionPolicy Bypass -File tools/cleanup_v313.ps1

3. Reconstruye y valida sobre TU dataset real:

   $env:PYTHONPATH="scripts"
   python scripts/v313/build_intelligence.py
   python -m unittest tests/test_v313.py
   python scripts/v313/validate_v313.py
   node --check assets/v313/intelligence.js
   node tests/ui_smoke_v313.js

4. Comprueba:

   git status

No hagas commit/push hasta revisar los recuentos y la nueva cola dinámica de investigación.
