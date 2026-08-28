UPDATE ONLY v3.9.0

1. Sustituye el contenido del proyecto por esta versión manteniendo tu carpeta `.git`.
2. Ejecuta:

   python -m unittest tests/test_v390.py
   PYTHONPATH=scripts python scripts/v39/build_intelligence.py
   python scripts/v39/validate_v39.py
   node --check assets/v390/intelligence.js
   node tests/ui_smoke_v390.js

3. Si todo pasa, publica en tu repo habitual.
4. Para reconstrucción automática usa `scripts/research_supervisor_v39.py`.
