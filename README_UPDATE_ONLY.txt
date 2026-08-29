UPDATE ONLY v3.12.0

IMPORTANTE: si la v3.11 está staged pero todavía no se ha hecho commit, NO hagas un commit intermedio.
La v3.12 puede instalarse directamente encima y terminar en un único commit v3.12.

1. Copia el contenido del ZIP encima del repositorio actual SIN borrar .git.

2. Si venías de la v3.11 staged, limpia los artefactos activos de la release intermedia:

   powershell -ExecutionPolicy Bypass -File tools/cleanup_v312.ps1

3. Reconstruye y valida sobre TU dataset real:

   $env:PYTHONPATH="scripts"
   python scripts/v312/build_intelligence.py
   python -m unittest tests/test_v312.py
   python scripts/v312/validate_v312.py
   node --check assets/v312/intelligence.js
   node tests/ui_smoke_v312.js

4. Comprueba después:

   git status

No hagas commit/push hasta revisar que los recuentos y las eliminaciones de fabricantes falsamente clasificados como mayoristas son coherentes.
