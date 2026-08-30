WESTCON IBERIA BUSINESS INTELLIGENCE · UPDATE ONLY v3.14.0

Baseline requerida: v3.13.0.

Opción recomendada:
1. Descomprime Westcon_v3.14.0_UPDATE_ONLY.zip fuera del repositorio.
2. Ejecuta:
   python aplicar_v314.py --repo "C:\Users\ivand\Downloads\estrategia"
3. El instalador exige que exista .git, comprueba VERSION=3.13.0 o 3.14.0, copia solo el payload v3.14 y ejecuta la validación.
4. Después:
   cd C:\Users\ivand\Downloads\estrategia
   python -m unittest tests/test_v314.py -v
   python scripts/v314/validate_v314.py
   node tests/ui_smoke_v314.js

No borra .git ni toca el remoto. No hace commit ni push.
