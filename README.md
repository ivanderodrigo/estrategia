# Westcon Iberia Business Intelligence v3.9.0

Release de producción candidata centrada en cuatro mejoras principales:

1. **Corrección de maquetación del header** para evitar el bloque blanco y el recorte de `Fuentes / Informe`.
2. **Nueva pestaña `Clientes`** entre Integradores y Tendencias.
3. **Cobertura de clientes públicos y privados ES/PT** con trazabilidad por campo.
4. **Responsive real** para desktop, tablet y móvil.

## Qué añade v3.9.0

- Orden de navegación: **Fabricantes · Mayoristas · Integradores · Clientes · Tendencias · Arquitecturas**.
- Clientes públicos: oportunidades de AAPP España/Portugal basadas en contratación, pliegos, perfiles del contratante y estrategia digital.
- Clientes privados: grandes cuentas ES/PT con señales de tecnología y renovación apoyadas en webs corporativas, informes e inteligencia procedente de empleo.
- Exportación PDF/PPT actualizada para incluir el nuevo bloque de clientes.
- Catálogo de fuentes ampliado con contratación pública (`PLACSP`, `TED`, `BASE.gov.pt`), planes digitales del sector público, grandes cuentas y portales de empleo corporativos.

## Validación rápida

```bash
python -m unittest tests/test_v390.py
PYTHONPATH=scripts python scripts/v39/build_intelligence.py
python scripts/v39/validate_v39.py
node --check assets/v390/intelligence.js
node tests/ui_smoke_v390.js
```

## Actualización automática

La capa pública v3.9.0 se reconstruye desde `scripts/research_supervisor_v39.py`.

- **Diaria**: incremental
- **Semanal**: profunda
- **Mensual**: exhaustiva

La publicación visible está en `data/v39/`.

## Estructura relevante

- `assets/v390/` → frontend v3.9.0
- `data/v39/` → dataset público v3.9.0
- `scripts/v39/` → construcción, pipeline y validación v3.9.0
- `config/v39/` → ampliaciones de fuentes y semillas de clientes
