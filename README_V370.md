# Westcon Iberia Business Intelligence v3.7.0

Aplicación estática de inteligencia estratégica para Westcon Iberia. Mantiene cinco áreas visibles: **Fabricantes, Integradores, Mayoristas, Tendencias y Arquitecturas**.

## v3.7.0

- Etiquetas semánticas uniformes: una misma categoría se representa siempre igual.
- Confianza por dato: verde (alta, ≥80%), amarillo (media, ≥60%), rojo (baja, ≥35%).
- Cada etiqueta conserva trazabilidad individual: porcentaje, motivo de confianza, fuente, descripción, fecha, método/tipo y enlace.
- Listas largas plegadas por defecto mediante `… +N`.
- Tablas ordenables por cabecera y columnas reordenables por arrastre; el orden se guarda localmente.
- Tendencias con esquema homogéneo y separación entre **mercado específico** y **mercado adyacente/contextual**.
- Trend Pulse y mapa de actores × tendencias, ambos síntesis propias basadas en evidencia y sin reproducir métricas propietarias de consultoras.
- Motor de investigación v3.7: más partner locators, páginas de alianzas, distribuidores, empleo/ATS, casos, premios, prensa de canal y búsqueda bidireccional fabricante↔partner.
- Las celdas vacías, los datos con confianza baja y las evidencias envejecidas generan una **cola interna de investigación** que eleva automáticamente el sondeo de la siguiente ejecución.
- La evidencia incorpora estado de vigencia, edad y ventana de revalidación cuando la fecha es normalizable; la antigüedad puede reducir la confianza hasta que se encuentre prueba más reciente.
- La publicación automática evita `pull --rebase` sobre JSON generados: reconcilia el resultado sobre el último `origin/main`, valida y reintenta el push si `main` cambia durante el workflow.
- Portfolio Iberia operativo aportado: portfolio base común España/Portugal; Proofpoint y Check Point adicionales en Portugal.
- PDF y PowerPoint mantienen el sistema visual de la web y añaden síntesis Trend Pulse.

## Fotografía incluida en la candidata

- 36 fabricantes Westcon Iberia.
- 100 integradores/partners con relación publicable y trazable.
- 15 mayoristas competidores.
- 15 tendencias con esquema homogéneo.
- 12 arquitecturas.
- 225 familias/fuentes de investigación.
- La cobertura seguirá creciendo automáticamente; la cola de huecos no se muestra al usuario.

## Validación local

```powershell
python -m unittest tests/test_v370.py
python scripts/v37/validate_v37.py
node --check assets/v370/intelligence.js
node tests/ui_smoke_v370.js
```

## Recolector

```powershell
python scripts/research_supervisor_v37.py --profile daily --skip-v33
```

Los workflows diario, semanal y mensual ejecutan la capa v3.7, conservan la última evidencia válida cuando una fuente externa falla y realimentan la siguiente ejecución con `data/v37/research_gaps.json`. Los perfiles deep/exhaustive disponen además de un reintento acotado si falla la investigación base.

## Instalación sobre v3.6.1

Usar preferentemente el paquete `UPDATE_ONLY`: copiar su contenido sobre el repositorio existente **sin borrar `.git` ni `data/v34`**, validar y subir con Git.
