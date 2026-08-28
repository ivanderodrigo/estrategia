# CHANGELOG v3.7.0

## Inteligencia y trazabilidad
- Publicación por niveles de confianza con umbral numérico y tres bandas visuales.
- Trazabilidad atómica por etiqueta; no se agregan fuentes ambiguas para listas.
- Publicación de evidencia media/baja cuando es trazable y explícitamente cualificada.
- Ampliación de relaciones partner/integrador y distribución mediante fuentes oficiales y señales públicas.

## Tendencias
- Misma estructura de campos para las 15 tendencias.
- Separación mercado específico vs. mercado adyacente.
- Panorama de actores ampliado con evidencia.
- Trend Pulse y mapa de actores × tendencias.

## UX
- Listas largas plegadas.
- Ordenación por cabecera y drag & drop de columnas.
- Etiquetas uniformes y coloreadas por confianza.
- PDF/PPT alineados con la web y Trend Pulse.

## Portfolio Iberia
- Regla operativa: portfolio base común ES/PT; Proofpoint y Check Point adicionales en PT.

## Actualización automática y vigencia
- Cola interna `data/v37/research_gaps.json`: huecos, confianza baja y evidencia envejecida alimentan las búsquedas siguientes.
- Revalidación automática con ventanas de vigencia y penalización controlada de confianza cuando toda la evidencia está antigua.
- Nuevas semillas oficiales de EfficientIP, LevelBlue y directorio Stratus/Penguin Solutions.
- Preflight de GitHub Actions corregido a tests/UI v3.7.
- Publicación robusta mediante `scripts/publish_research_update.py`: snapshot de datos, refresh contra último `origin/main`, validación y reintentos sin rebase de JSON generados.
- Fallback acotado en perfiles semanales/mensuales si la investigación base falla.

## Enriquecimiento de la candidata
- Snapshot inicial ampliada a 100 integradores/partners y 15 mayoristas competidores.
- Relaciones enriquecidas con evidencias actuales o fechadas de EfficientIP, FireMon, Ivanti, RUCKUS, Avaya, Ciena, Zscaler y Okta, entre otras.
- Directorios/casos oficiales añadidos como semillas para el sondeo automático posterior.
- Etiqueta de tendencia normalizada a `AI-ready Data Center / Fabric / Edge`.
