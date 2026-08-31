# Tests realizados — v3.19.0

Resultado final antes del empaquetado:

- Python unittest: **18/18 PASS**.
- `scripts/validate.py`: **PASS**.
- `node --check assets/app/intelligence.js`: **PASS**.
- `node tests/ui_smoke_v319.js`: **PASS**.
- Workflows: referencias Python existentes y ausencia de runtime `vXXX`: **PASS**.
- Data quality: Comstor, Forescout, fabricante≠mayorista, aliases, relaciones con URL, arista canónica única, linecards sin duplicados, gaps estrictos y guiones pendientes: **PASS**.
- Frontend común: Fabricantes, Integradores, Mayoristas, Clientes públicos y privados usan el mismo motor de tabla con reorder/visibility/width/persistencia: **PASS**.
- UPDATE_ONLY sobre copia Git limpia de v3.18: **PASS**; 474 archivos legacy versionados retirados, `.git` preservado, `VERSION=3.19.0`, validaciones posteriores PASS.
- Rollback forzado mediante payload inválido: **PASS**; restauró `VERSION=3.18.0` y `git status` limpio.
