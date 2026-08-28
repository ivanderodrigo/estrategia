# Westcon Iberia Business Intelligence v3.8.2

Release de corrección de modelado competitivo sobre v3.8.1.

## Corrección principal

- **Comstor se modela como unidad especializada Cisco de Westcon**, no como mayorista competidor.
- Se elimina Comstor de la tabla pública de Mayoristas.
- Se elimina Comstor de los campos «Mayoristas alternativos» de los fabricantes.
- Las referencias a Westcon-Comstor se conservan cuando son fuente, contexto Iberia o evidencia propia de Westcon; no se borran del conocimiento.
- La regla se aplica en el generador, no solo en el JSON actual, por lo que se mantiene en las actualizaciones automáticas.
- Tests y validador bloquean tanto `Westcon` como `Comstor` si vuelven a aparecer como competencia.

## Se conserva de v3.8.1

- Tarjetas de Tendencias contenidas y listas plegables.
- Westcon Trend Loop y Vendor Arena con explicación de lectura.
- Ayuda global de confianza y razones concretas por dato.
- Actualización automática diaria/semanal/mensual y revalidación de huecos.

## Validación

```powershell
python -m unittest tests/test_v382.py
python scripts/v38/validate_v38.py
node --check assets/v382/intelligence.js
node tests/ui_smoke_v382.js
python scripts/test_resilience.py
python scripts/test_schedule.py
```
