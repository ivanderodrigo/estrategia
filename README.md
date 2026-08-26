# Westcon Iberia · Radar Estratégico Tecnológico v1.2

**Edición ejecutiva · Motor de recomendación v2 · Inteligencia pública**

Aplicación estática para GitHub Pages. La filosofía es deliberada: **muy sencilla delante y muy profunda detrás**. Parte del portfolio/taxonomía de la presentación FY27 facilitada y lo cruza con información pública externa sobre mercado, canal, fabricantes, analistas, M&A, producto, servicios y tendencias.

## Qué ves de un vistazo

Por fabricante:

- decisión calculada: **ACELERAR / CONSTRUIR / DEFENDER / OPTIMIZAR / INVESTIGAR**;
- score de oportunidad;
- principales fabricantes competidores;
- otros mayoristas públicamente demostrados en España y Portugal;
- señales públicas de Gartner, IDC, Forrester y otras consultoras;
- sinergias con el resto del portfolio;
- nivel de solape/canibalización;
- confianza de la evidencia;
- acción recomendada a 30, 90 y 180 días.

La vista **Ver datos** despliega la profundidad del motor sin cargar la pantalla ejecutiva.

## Motor de recomendación v2

La recomendación ya no depende de una prioridad escrita a mano. Se recalcula con:

- 24% momentum de mercado;
- 16% encaje con el portfolio;
- 14% potencial de sinergia;
- 12% recurrencia;
- 12% diferenciación;
- 10% señal pública de analistas;
- 7% palanca de servicios;
- 5% calidad de evidencia.

El riesgo se calcula con:

- 45% solape interno;
- 35% presión competitiva del canal;
- 20% gap de evidencia pública.

Las ponderaciones están en `config/strategy_engine.json` y pueden modificarse sin tocar la interfaz.

## Capa de datos

- `data/base.json`: portfolio y taxonomía de partida.
- `data/vendor_intelligence.json`: baseline estratégico curado.
- `data/curated_evidence.json`: evidencias públicas de alta confianza.
- `data/research.latest.json`: última investigación automatizada + cobertura + gaps.
- `data/history/`: snapshots históricos.
- `config/source_registry.json`: jerarquía y confianza de fuentes.
- `config/research_queries.json`: consultas rotatorias de investigación.
- `config/strategy_engine.json`: reglas y pesos del motor.

## Investigación automática

`.github/workflows/research.yml` ejecuta `scripts/research.py` semanalmente.

El colector busca y clasifica por fabricante:

- distribución y mayoristas ES/PT;
- Gartner, IDC, Forrester, Omdia, Canalys, Dell’Oro, Synergy e ISG;
- market share, tamaño y crecimiento de mercado;
- adquisiciones y movimientos corporativos;
- expansión de plataformas y lanzamientos;
- servicios, soporte, marketplaces y programas de canal;
- tendencias estratégicas generales 2026–2030.

Además calcula automáticamente:

- cobertura por fabricante;
- gaps de investigación;
- diversidad de fuentes;
- señales de canal;
- señales de analistas;
- distribución de evidencias por tipo, fuente y geografía.

Sin API key utiliza Google News RSS como discovery. `BRAVE_SEARCH_API_KEY` es **opcional** y solo amplía la búsqueda; no es necesaria ni para instalar ni para ejecutar la aplicación.

## Reglas de evidencia

- Solo información pública externa + presentación FY27 facilitada.
- Sin revenue, margen, pipeline, CRM, personas ni información interna.
- EMEA **no** se convierte automáticamente en Iberia.
- Iberia **no** se convierte automáticamente en España y Portugal si la fuente no lo soporta.
- “No demostrado” no significa “no existe”.
- Search/discovery no se eleva a evidencia ejecutiva hasta validarse contra fuente pública suficientemente fiable.
- No se reconstruyen posiciones de Magic Quadrants, Waves o MarketScapes licenciados si no son públicas.

## Instalación / actualización desde VS Code

Si ya tienes el repositorio clonado, sustituye los archivos por esta versión y ejecuta:

```bash
git add .
git commit -m "Radar estrategico v1.2 - motor de recomendacion v2"
git push
```

GitHub Pages se actualizará automáticamente.

Para una instalación nueva: sube el contenido de esta carpeta a la raíz del repositorio y activa `Settings → Pages → Deploy from a branch → main → /(root)`.

## Estilo

Mantiene la estética ejecutiva de la presentación FY27: azul marino, blanco, Corbel/Arial y acentos naranja, magenta, turquesa y azul. La prioridad visual es que Dirección pueda entender la situación en segundos.
