# Westcon Iberia Decision Intelligence v3.3.0
## Ecosystem Intelligence Engine

v3.3.0 se instala sobre la baseline estable v3.2.6/v3.2.7. Mantiene el motor Evidence & Event Intelligence y añade una capa específica para entender el ecosistema de canal y convertirlo en inteligencia de negocio.

### Qué incorpora

- Tablas de Mayoristas e Integradores con profundidad comparable a Fabricantes.
- Campos de negocio más ricos y lenguaje natural.
- Ocultación automática de columnas completamente vacías.
- Selección, reordenación mediante drag & drop y ordenación por cualquier columna.
- Botones globales A− / A / A+ para tamaño de texto, persistentes en el navegador.
- Trazabilidad por dato: hover sobre una celda explica cómo se obtuvo y qué fuentes públicas la soportan.
- Ayuda `?` en etiquetas de columna para explicar scores y conceptos no evidentes.
- Investigación dirigida a los gaps de Mayoristas e Integradores mediante Google News RSS gratuito, además de la evidencia v3.1/v3.2 ya existente.
- Integrator × Vendor Matrix con estados conservadores: CONFIRMED_RELATION, PROBABLE_RELATION, WHITESPACE_RESEARCH_PRIORITY e INSUFFICIENT_PUBLIC_EVIDENCE.
- Distributor × Vendor Matrix para presión y solape de canal.
- Vendor Pair Intelligence para sinergias y potencial solape funcional entre fabricantes del portfolio.
- Arquitecturas originales de estilo analista en SVG: SASE/Zero Trust, AI-ready SecOps, Hybrid Cloud/Data Center, Secure Networking/NaaS e Identity-first Security.
- Arquitecturas orientadas a negocio: outcomes, plays monetizables y preguntas para Dirección/preventa.
- Vista ejecutiva 16:9 e impresión/PDF con una estética más clara para informes y presentaciones.

### Principios de rigor

- Ausencia de evidencia pública no equivale a ausencia de relación.
- Las inferencias se etiquetan como investigación; no se presentan como hechos.
- Los scores de negocio/económicos son relativos hasta incorporar ventas, margen, pipeline y rebates internos.
- Los diagramas son originales; no reproducen arte propietario de Gartner u otras consultoras.

### Instalación

Copiar el contenido del ZIP encima de la raíz del repositorio y reemplazar archivos coincidentes. No borrar `.git`, `.venv` ni `data`.

```powershell
python tools/aplicar_v330.py
Get-Content VERSION
python tests/test_v330_unittest.py
node --check assets/v330/ecosystem-intelligence.js
```

La versión debe ser `3.3.0`.

### Prueba rápida sin repetir v3.2

```powershell
python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32
```

Genera:

- `data/v33/ecosystem_profiles.json`
- `data/v33/integrator_vendor_matrix.json`
- `data/v33/distributor_vendor_matrix.json`
- `data/v33/vendor_pair_intelligence.json`
- `data/v33/architectures.json`
- `data/v33/targeted_evidence.json`
- `data/v33/last_run.json`

### Ejecución integral

Cuando la prueba corta sea correcta:

```powershell
python scripts/research_supervisor_v33.py --profile daily --max-runtime 720
```

Los workflows daily/weekly/monthly se actualizan para utilizar `research_supervisor_v33.py` y persistir `data/v33/`.
