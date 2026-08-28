# Westcon Iberia Business Intelligence v3.8.0

Aplicación estática para GitHub Pages centrada exclusivamente en **Fabricantes, Integradores, Mayoristas, Tendencias y Arquitecturas**. No publica recomendaciones.

## v3.8.0

- Tablas legibles con ancho mínimo semántico por columna, scroll horizontal antes de comprimir y primera columna fija.
- Etiquetas compactas en una línea, truncado visual y detalle completo en hover; las listas largas muestran `… +N` y se expanden por celda.
- Confianza atómica por etiqueta: verde (alta), amarillo (media) y rojo (baja), siempre con porcentaje y fuente individual.
- Columnas extremadamente dispersas se ocultan temporalmente hasta alcanzar cobertura útil; sus huecos siguen alimentando la cola interna de investigación.
- **Westcon Trend Loop** y **Westcon Vendor Arena** usan marcadores numerados y leyendas con nombres completos para evitar solapamientos. PDF y PPT aplican el mismo principio.
- Tendencias mantienen un esquema homogéneo y separan métricas del mercado específico de métricas adyacentes/contextuales.
- Investigación v3.8 más exhaustiva: partner locators/directorios, sitemaps oficiales, páginas de alianzas, linecards, casos, premios, certificaciones, empleo/ATS, prensa, analistas públicos, contratación ES/PT y Common Crawl como descubrimiento con revalidación en vivo.
- Las páginas oficiales de partners pueden descubrir actores long-tail fuera del universo precargado; se publican inicialmente con confianza limitada hasta corroboración recíproca.
- Celdas vacías, datos rojos/amarillos y evidencias envejecidas generan automáticamente nuevas consultas en ejecuciones posteriores.
- Actualización automática diaria, semanal profunda y mensual exhaustiva con publicación resiliente sobre el último `origin/main`.
- Regla de portfolio: España = portfolio base; Portugal = mismo portfolio + Proofpoint + Check Point.

## Validación local

```powershell
python -m unittest tests/test_v380.py
python scripts/v38/validate_v38.py
node --check assets/v380/intelligence.js
node tests/ui_smoke_v380.js
python scripts/test_resilience.py
python scripts/test_schedule.py
```

## Actualización automática

Los workflows `research-daily.yml`, `research-weekly.yml` y `research-monthly.yml` ejecutan `research_supervisor_v38.py`. `data/v38/research_gaps.json` es una cola interna de realimentación: no se muestra al usuario final, pero aumenta el sondeo de campos incompletos, débiles o envejecidos.

`publish_research_update.py` conserva las salidas generadas, refresca el checkout contra el último `origin/main`, restaura solo los datos automáticos, valida v3.8 y reintenta el push si `main` avanza durante la publicación.
