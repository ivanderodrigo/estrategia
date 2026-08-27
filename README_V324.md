# Westcon Iberia Decision Intelligence v3.2.4

Hotfix de robustez y observabilidad sobre v3.2.3.

## Cambios

- Corrige el fallo real del conector PLACSP Atom: una referencia interna a `base` podía lanzar `NameError` después de parsear correctamente el feed.
- PLACSP/Atom incorpora dos intentos acotados y caché de último resultado oficial válido; un fallo temporal no borra la inteligencia previa.
- Los probes de RSS/Atom distinguen `no_feed` de un error de un feed previamente conocido. Un dominio sin RSS no se reporta como fuente rota.
- `quality_report.json` resume tasa de decisiones, evidencia, concentración de fuentes, presión competitiva y shortlist de whitespace.
- La presión competitiva publica `HIGH/MEDIUM` y alertas separadas; no se fabrican amenazas para elevar una métrica.
- Whitespace conserva el backlog completo, pero añade shortlist de hasta 25 candidatos HIGH/MEDIUM para investigación.
- El briefing muestra `medium-econ` y `max-econ`; `high-econ=0` ya no se interpreta como error cuando ninguna decisión cruza el umbral.

## Filosofía

La v3.2.4 no relaja los umbrales para conseguir más oportunidades o amenazas. Hace visible si no existe evidencia suficiente. La aplicación debe preferir `0 amenazas confirmadas` a inventar una.
