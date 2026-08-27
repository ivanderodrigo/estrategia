# Westcon Iberia Decision Intelligence v3.3.1

## Objetivo
Profundizar la v3.3.0 a partir de la auditoría real: la búsqueda dirigida estaba concentrándose en los primeros mayoristas, la matriz mayorista×fabricante no exponía estados, los scores de whitespace mezclaban escalas y la cobertura de perfiles no era visible.

## Cambios principales
- Investigación adaptativa por huecos de información y reparto justo entre entidades.
- Daily: hasta 180 queries; weekly 480; monthly 1100, con presupuesto temporal controlado.
- Cuota específica para verificar pares integrador×fabricante prioritarios.
- Métricas por dimensión, entidad y grado de fuente.
- `ecosystem_profiles.json` incluye también una colección `profiles` aplanada para auditoría.
- Cobertura de perfil, gaps de investigación, diversidad de fuentes y Evidence Grade A–D.
- Nuevos indicadores de negocio: prioridad de activación, prioridad de respuesta competitiva, potencial de servicios recurrentes y tracción pública.
- Matriz integrador×fabricante con `priority_score` consistente, grado de evidencia y siguiente investigación.
- Matriz mayorista×fabricante con estados explícitos de relación pública.
- Vendor pairs con `overlap_score`, fuerza de evidencia, integradores compartidos y preparación de play comercial.
- Arquitecturas con fuerza de evidencia no saturada, cobertura por capas, integradores compatibles, readiness comercial y gaps.
- `coverage_report.json` y `research_plan.json` para que las siguientes ejecuciones inviertan más donde el sistema sabe menos.
- UI ampliada con columnas de negocio y trazabilidad; las columnas sin datos siguen ocultándose automáticamente.

## Instalación
Copiar el contenido sobre el repositorio existente, reemplazando archivos coincidentes, y ejecutar:

```powershell
python tools/aplicar_v331.py
Get-Content VERSION
python tests/test_v331_unittest.py
node --check assets/v331/ecosystem-intelligence.js
python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32
```

`VERSION` debe mostrar `3.3.1`.
