# Westcon Iberia Business Intelligence v3.8.2

Aplicación estática para GitHub Pages centrada exclusivamente en **Fabricantes, Integradores, Mayoristas, Tendencias y Arquitecturas**, con inteligencia descriptiva trazable y sin salidas prescriptivas.

## v3.8.2

- Tarjetas de Tendencias contenidas y legibles: cada fila mantiene su espacio, las listas se pliegan con `… +N` y los textos extensos con `Ver más`.
- **Westcon Trend Loop** explica de forma visible qué significan Emergente, Aceleración, Escala y Consolidación, además de madurez, momentum y urgencia.
- **Westcon Vendor Arena** explica ejes, cuadrantes, utilidad y límites: mide presencia documentada en el dataset, no cuota ni liderazgo comercial.
- Estado visible de **actualización automática** desde la cabecera: última publicación, ciclo, cobertura y huecos que siguen investigándose.
- Ayuda global de **Confianza** con umbrales: alta 80–99%, media 60–79%, baja 35–59%; por debajo del 35% no se publica.
- Confianza explicable por dato: el hover muestra razones concretas, porcentaje, fuentes, fecha, tipo/método, vigencia, revalidación y enlace.
- Los datos medios/bajos indican explícitamente qué limita la confianza y qué evidencia adicional permitiría elevarla.
- Se mantiene el motor v3.8 de búsqueda exhaustiva, realimentación de huecos y revalidación automática.
- Regla de portfolio: España = portfolio base; Portugal = mismo portfolio + Proofpoint + Check Point.
- Regla de canal: **Comstor = unidad especializada Cisco de Westcon**, por lo que no aparece como mayorista competidor ni como mayorista alternativo de fabricantes.

## Validación local

```powershell
python -m unittest tests/test_v382.py
python scripts/v38/validate_v38.py
node --check assets/v382/intelligence.js
node tests/ui_smoke_v382.js
python scripts/test_resilience.py
python scripts/test_schedule.py
```

## Actualización automática

Los workflows `research-daily.yml`, `research-weekly.yml` y `research-monthly.yml` ejecutan el supervisor v3.8 y validan la capa v3.8.2 antes de publicar.

- **Diaria · 06:23 Madrid**: cambios recientes, nuevas relaciones, empleo, casos y revalidación rápida.
- **Semanal · domingo 04:47**: locators, webs de integradores/mayoristas, certificaciones, servicios, casos, empleo y fuentes sectoriales.
- **Mensual · día 1 03:17**: long-tail, huecos persistentes, nuevas entidades, tendencias, arquitecturas y evidencia envejecida.

`data/v38/research_gaps.json` mantiene la cola interna que eleva el sondeo de celdas vacías y señales de confianza limitada. `publish_research_update.py` publica sobre el último `origin/main` y reintenta si la rama cambia durante la actualización.
