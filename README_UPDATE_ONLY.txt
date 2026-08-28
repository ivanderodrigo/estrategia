UPDATE ONLY v3.8.2

Copiar todo el contenido de este paquete sobre el repositorio v3.8.1 existente, sin borrar nada y conservando .git.

La actualización mantiene las mejoras visuales y de confianza de v3.8.1 y corrige el modelado competitivo de Comstor: es la unidad especializada Cisco de Westcon y no se publica como mayorista competidor.

El paquete incremental no sustituye históricos ajenos a los archivos incluidos. Después ejecutar:

  git status

Validación recomendada:

  python -m unittest tests/test_v382.py
  python scripts/v38/validate_v38.py
  node --check assets/v382/intelligence.js
  node tests/ui_smoke_v382.js
  python scripts/test_resilience.py
  python scripts/test_schedule.py

Después: git add -A, commit, git pull --rebase origin main y git push origin main.
