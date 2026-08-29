UPDATE ONLY v3.11.0

1. Copia el contenido del ZIP encima del repositorio actual sin borrar `.git`.
2. Como la v3.10 llegó a estar staged, ejecuta la limpieza de las funciones retiradas:

   powershell -ExecutionPolicy Bypass -File tools/cleanup_v311.ps1

3. Reconstruye y valida:

   $env:PYTHONPATH="scripts"
   python scripts/v311/build_intelligence.py
   python -m unittest tests/test_v311.py
   python scripts/v311/validate_v311.py
   node --check assets/v311/intelligence.js
   node tests/ui_smoke_v311.js

4. Ejecuta `git add -A` y revisa `git status` antes de commit/push.
