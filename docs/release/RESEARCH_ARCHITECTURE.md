# Arquitectura del motor de investigación

1. Gap estricto → tarea activa.
2. Prioridad por impacto de negocio y yield histórico.
3. Dominio oficial y secciones internas primero.
4. Sitemap/PDF/catálogos/linecards/partners/careers.
5. Fuentes oficiales de entidades relacionadas y directorios de fabricante.
6. Contratación pública, casos de éxito, empleo y prensa especializada.
7. Español, portugués e inglés; aliases y nombres históricos.
8. Nuevas entidades generan nuevas tareas.
9. Candidatos débiles no ascienden a hechos.
10. Grafo propaga evidencia compatible en ambos sentidos.
11. Ledger y learning son internos; Pages publica únicamente resultados ejecutivos.

El plan de estrategias está normalizado: cada gap guarda un `strategy_profile` y un `next_pass`, no 48 copias de las mismas queries. Las queries se generan bajo demanda, y las ejecuciones se registran en `research_ledger.json`.
