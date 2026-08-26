# Westcon Iberia · Radar Estratégico Tecnológico v1.1

**Edición ejecutiva · Inteligencia pública**

Aplicación estática para GitHub Pages que transforma el portfolio FY27 de Westcon España en un cockpit de estrategia tecnológica para Iberia. La interfaz está diseñada para ser muy simple y ejecutiva; la capa de investigación es deliberadamente más profunda.

## Qué muestra de un vistazo

Para cada fabricante del portfolio:

- prioridad estratégica: **ACELERAR / CONSTRUIR / OPTIMIZAR**;
- principales fabricantes competidores;
- otros mayoristas públicamente verificados en España y/o Portugal;
- señales públicas de Gartner, IDC, Forrester y otras consultoras;
- sinergias con otros fabricantes Westcon;
- overlaps internos del portfolio;
- acción recomendada para explotar la oportunidad o reducir conflicto;
- enlaces a las evidencias públicas.

Incluye además radar 2026–2030, mapa de sinergias, cambios externos relevantes, biblioteca de fuentes y generación de PDF y PowerPoint.

## Política de datos

La aplicación utiliza exclusivamente:

1. información pública accesible externamente;
2. el portfolio, taxonomía y capacidades descritas en la presentación FY27 facilitada para este proyecto.

No solicita ni almacena revenue, margen, pipeline, forecast, MDF, personas, carga de preventa, CRM ni ningún otro dato interno.

Una relación EMEA **no se extrapola automáticamente** a España o Portugal. La ausencia de un mayorista en la base significa **“no demostrado todavía”**, no exclusividad.

## Instalación en GitHub Pages

1. Crea un repositorio en GitHub.
2. Sube **el contenido de esta carpeta** a la raíz del repositorio. `index.html` debe quedar en la raíz.
3. Ve a `Settings → Pages`.
4. Selecciona `Deploy from a branch`.
5. Branch: `main`; Folder: `/ (root)`.
6. Guarda.

La aplicación no necesita backend ni API para funcionar.

## Investigación automática

El workflow `.github/workflows/research.yml` ejecuta `scripts/research.py` periódicamente.

La investigación genera queries por fabricante para:

- Westcon y presencia pública ES/PT;
- distribuidores en España y Portugal;
- Arrow, TD SYNNEX, Exclusive, Infinigate, V-Valley e Ingram Micro;
- Gartner, Forrester, IDC, Omdia, Canalys, Dell’Oro y Synergy Research;
- market share;
- competidores;
- adquisiciones;
- estrategia de plataforma;
- lanzamientos 2025–2026;
- servicios, soporte, marketplace y programas de canal.

Sin API key usa Google News RSS como discovery limitado. Si se añade opcionalmente `BRAVE_SEARCH_API_KEY` como GitHub Actions Secret, aumenta la amplitud de búsqueda. **Brave no es necesario para instalar ni utilizar la aplicación.**

## Gobernanza de evidencia

- `data/vendor_intelligence.json`: baseline ejecutivo curado.
- `data/curated_evidence.json`: evidencias públicas validadas.
- `data/research.latest.json`: discovery dinámico.
- `data/history/`: snapshots de investigación.

Un resultado de búsqueda no se trata automáticamente como verdad ejecutiva. Las conclusiones relevantes deben quedar vinculadas a una fuente primaria pública o a un resumen público de analista.

## Estilo visual

La v1.1 toma como referencia visual la presentación FY27 facilitada: Corbel/Arial, azul marino, blanco y acentos naranja, magenta, turquesa y azul.
