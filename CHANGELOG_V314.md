# CHANGELOG · v3.14.0

## Added
- Columnas de Mayoristas: `revenue`, `competitor_vendor_overlap`, `differential_capabilities`.
- Etiqueta explícita `Fabricantes coincidentes con Westcon` para `westcon_overlap`.
- 16 fuentes/familias adicionales orientadas a facturación, capacidades de mayoristas y peers de fabricantes.
- Enriquecimiento de facturación 2025 para 14 mayoristas españoles.
- Enriquecimiento de competidores/peers para 11 fabricantes con gap previo.
- Gap engine v3.14 con `CORE_TARGET_FIELDS`, `OPTIONAL_FIELDS` y `optional_missing_by_field`.
- UI `missingMarkup()` para separar gap crítico de ausencia opcional.
- Tests v3.14 (26 tests) y smoke test Node.
- Supervisor/pipeline/validator v3.14.

## Changed
- Encabezados de todas las secciones reescritos como descripciones claras del contenido y utilidad de cada vista para el usuario; las reglas de modelado quedan fuera de la cabecera.
- Columnas decisionales permanecen visibles aunque todavía falte evidencia.
- Columnas opcionales escasas siguen ocultándose con umbral de cobertura.
- `scripts/research.py` consume la cola actual `data/v314/research_gaps.json`.
- Procurement live de v3.14 escribe en `data/v314`.
- Workflows diaria/semanal/mensual y Pages actualizados a v3.14.
- Exportación PDF/PPT renombrada a v3.14.0.

## Preserved business rules
- Comstor no es mayorista competidor.
- Fabricantes quedan fuera de Mayoristas aunque exista venta directa.
- Forescout no es fabricante activo del portfolio Westcon.
- IBEX 35 + PSI completos como universo privado mínimo.
- Vacantes nunca prueban una relación de partner.
- Contratación pública exige anuncio/expediente concreto.
- Ausencia pública no equivale a inexistencia.
