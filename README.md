# Westcon Iberia Business Intelligence v3.11.0

Release centrada en precisión de roles, usabilidad de trazabilidad y reporting ejecutivo.

## Cambios principales

- **Mayoristas estrictos:** un fabricante Westcon nunca se publica dentro de la tabla Mayoristas. Si existe evidencia explícita de venta directa, se muestra un indicador `Venta directa` junto al nombre del fabricante.
- **Tooltips y trazabilidad por encima de toda la UI:** tanto las ayudas `?` como las fichas `i` se portan a una capa global `fixed` para evitar que otras filas, etiquetas o scrollbars las tapen.
- **Tarjetas grandes desplazables:** el scroll ya no cierra la ficha de trazabilidad; la tarjeta se reposiciona y mantiene su propio scroll.
- **Ingesta y aportaciones manuales retiradas de la versión activa:** no aparecen en la UI, en el catálogo activo ni en los workflows v3.11.
- **PDF reescrito:** deja de depender de renderizar HTML con `html2pdf` y pasa a un informe nativo con jsPDF, usando la misma lógica ejecutiva del PowerPoint: portada, lectura ejecutiva, dominios y metodología.
- **PowerPoint ejecutivo preservado**, con anexo detallado opcional.

## Validación

```powershell
$env:PYTHONPATH="scripts"
python scripts/v311/build_intelligence.py
python -m unittest tests/test_v311.py
python scripts/v311/validate_v311.py
node --check assets/v311/intelligence.js
node tests/ui_smoke_v311.js
```

## Automatización

Los workflows diario, semanal y mensual llaman a `scripts/research_supervisor_v311.py` y publican `data/v311/`.
