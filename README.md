# Westcon Iberia · Radar Estratégico Tecnológico v1.4

**Deep Intelligence Edition · Motor de recomendación v4 · España + Portugal · Solo inteligencia pública**

Aplicación estática para GitHub Pages. La interfaz sigue siendo deliberadamente simple; el salto de esta versión está en lo que no se ve: acumulación de evidencia, más fuentes, búsqueda pairwise contra competidores, contratación pública, ecosistema de integradores/clientes, corroboración, detección de cambios y un motor ofensivo de recomendaciones.

La configuración de portfolio parte de la presentación FY27 facilitada y de las correcciones de alcance del proyecto. El motor de investigación no utiliza revenue, margen, pipeline, CRM, personas, objetivos ni otra información interna.

## Profundidad de investigación v4.2

La v4.2 amplía el subsuelo de datos sin añadir complejidad visual:

- contratación pública europea mediante TED Search API;
- contratación española mediante datasets oficiales PLACSP, con soporte XLSX y feeds técnicos Atom/ZIP;
- contratación portuguesa mediante recursos públicos Portal BASE / IMPIC publicados en dados.gov.pt, con soporte JSON, CSV, XLSX y ZIP;
- rastreo de sitemaps oficiales de fabricantes, mayoristas, integradores y consultoras;
- Google News RSS, GDELT y Arquivo.pt como discovery complementario;
- consultas vendor × país × mayorista × integrador × cliente × vertical × competidor;
- comparativas pairwise para displacement, migración, TCO, casos y partners compartidos;
- score de evidencia por autoridad, geografía, frescura, corroboración y directness;
- grafo competitivo y matriz de ataque por fabricante/competidor;
- priorización adaptativa de búsquedas: los gaps reciben más presupuesto en la siguiente ejecución;
- control de calidad previo al commit automático: si el dataset falla, no se publica.

El motor mantiene Juniper Networks como `COMPETITOR_TRACKED`, no como fabricante activo de Westcon Iberia, y contempla TD SYNNEX España como presión pública de canal para Extreme Networks.

## Qué responde por fabricante

En segundos:

- **qué decisión tomar:** ACELERAR / CONSTRUIR / DEFENDER / OPTIMIZAR / INVESTIGAR;
- qué mercado y tendencias lo impulsan;
- cuáles son sus principales fabricantes competidores;
- qué otros mayoristas aparecen demostrados en España y Portugal;
- qué integradores/partners tienen capacidad pública demostrable;
- qué clientes finales públicos y adjudicaciones existen;
- qué dicen públicamente Gartner, IDC, Forrester, Omdia, Canalys, Dell'Oro, Synergy e ISG;
- con qué vendors Westcon tiene sinergias y dónde existe overlap;
- qué gaps competitivos parecen atacables;
- **qué iniciativas Westcon utilizar** para atacar la competencia;
- plan recomendado a 30, 90 y 180 días.

`Ver datos` abre el razonamiento completo sin recargar la vista ejecutiva.

## Motor de recomendación v4

El motor separa tres cosas:

1. **Oportunidad estratégica** — mercado, portfolio fit, recurrencia, diferenciación, sinergias, analistas, servicios, ecosistema, clientes e integradores.
2. **Riesgo** — overlap, presión de canal, intensidad competitiva, concentración de partners/clientes, frescura, desequilibrio ES/PT y gaps de evidencia.
3. **Potencial de ataque** — combina oportunidad, presión competitiva, whitespace, sinergias, servicios, integradores, clientes, solapes explotables y fiabilidad de los datos.

La recomendación no sale de una única suma. Usa gates condicionales y un modelo de incertidumbre: cuando faltan datos, el score se contrae hacia una posición neutral en lugar de fingir precisión.

### Ataque competitivo

Las recomendaciones convierten gaps en acciones con las iniciativas de Westcon:

- **BLUEPRINT** — benchmark, vendor linkage, upskill, ejecución, PoC, resell, implementación y lifecycle;
- **3D Labs** — demo, validación, PoC alternativo y time-to-value;
- **Tech Xpert** — preferencia técnica, comunidad y enablement;
- **Tech Assessments** — discovery y evidencia de riesgo;
- **FLEX** — OPEX, financiación y propuesta multivendor;
- **Intelligent Demand** — ABM, intención y generación de demanda;
- **Servicios Westcon** — diseño, staging, despliegue, educación, soporte y managed services;
- **Lifecycle / ServiceView** — adopción, expansión, renovación y refresh;
- **GSCS** — despliegue global y proyectos cross-border;
- **Cloud Marketplaces** — recurrencia, private offers y route-to-market cloud.

El motor no afirma que un competidor carece de una capacidad solo porque no encuentre evidencia. Lo expresa como **gap aparente / hipótesis a validar** y aumenta la investigación antes de convertirlo en una conclusión ejecutiva.

## Investigación mucho más profunda

### 1. Web / noticias / histórico

- Brave Search API, si existe `BRAVE_SEARCH_API_KEY`;
- Google News RSS;
- GDELT DOC 2.0 para noticias globales;
- Arquivo.pt para histórico web y cambios de canal/partner, especialmente Portugal.

### 2. Fuentes primarias

El motor rastrea sitemaps y páginas de alto valor de:

- fabricantes;
- principales mayoristas;
- integradores y consultoras;
- páginas públicas de analistas.

Busca partner locators, linecards, casos de cliente, premios, especializaciones, servicios, soporte, formación, marketplaces, referencias, noticias y páginas sectoriales.

### 3. Contratación pública

- **TED Search API** para España y Portugal;
- **Plataforma de Contratación del Sector Público / Hacienda** mediante los feeds oficiales de datos abiertos;
- **dados.gov.pt / Portal BASE / IMPIC** para contratos y anuncios portugueses.

Estas fuentes permiten descubrir organismos compradores, integradores/adjudicatarios, tecnologías citadas, verticales y referencias reales incluso cuando no existe un caso de éxito comercial publicado.

### 4. Investigación competitiva pairwise

Para cada fabricante se generan búsquedas directas frente a sus competidores, por ejemplo:

`Extreme ↔ Cisco · España · replacement / migration / TCO`

`Extreme ↔ HPE Networking / Juniper · Portugal · displacement / case study`

Esto alimenta battlecards, integradores compartidos, clientes con tecnologías rivales y tácticas de ataque.

### 5. Ecosistema Iberia

Se investigan y ponderan:

- integradores certificados;
- Partner of the Year / premios oficiales;
- MSSP y managed services;
- especializaciones;
- casos conjuntos vendor + integrador + cliente;
- adjudicaciones públicas;
- referencias finales por sector;
- diversidad y concentración del ecosistema;
- integradores compartidos entre vendors;
- clientes con señales multivendor o de competencia.

Un caso cliente o una adjudicación pesan más que una simple aparición en un directorio.

## Autoactualización

No hay que actualizar los datos manualmente.

### Diaria

`.github/workflows/research-daily.yml`

Ejecuta una pasada ligera todos los días para detectar:

- nuevos mayoristas / cambios de distribución;
- partners e integradores;
- clientes y casos;
- M&A;
- producto/plataforma;
- noticias competitivas;
- señales recientes de contratación.

### Semanal profunda

`.github/workflows/research-weekly.yml`

Cada domingo realiza la pasada exhaustiva:

- hasta 1.200 queries si Brave está configurado;
- hasta 360 sin Brave;
- crawling de sitemaps de fabricantes, mayoristas e integradores;
- analistas públicos;
- TED;
- PLACSP;
- dados.gov.pt / BASE;
- competencia pairwise;
- recalibración de gaps y cobertura.

Los minutos del cron son deliberadamente no redondos para reducir colas de GitHub Actions.

## El sistema acumula conocimiento

`research.latest.json` ya no se reconstruye desde cero en cada ejecución. Conserva evidencia anterior dentro de una ventana temporal y la mezcla con nuevos hallazgos.

Además genera:

- `data/research_status.json` — salud del motor y cobertura;
- `data/changes.latest.json` — nuevas relaciones y cambios materiales;
- `data/history/snapshot-*.json` — histórico ligero para detectar evolución;
- conflictos a validar cuando aparece evidencia contradictoria.

La siguiente ejecución da más presupuesto a vendors con baja cobertura. El objetivo es que el motor **busque más justo donde menos sabe**.

## Modelo de evidencia

Cada evidencia se puntúa por:

- autoridad de la fuente;
- frescura;
- precisión geográfica;
- relación directa con la afirmación;
- corroboración independiente;
- diversidad de fuentes;
- especificidad.

Jerarquía general:

1. reguladores / contratación pública;
2. fabricantes, mayoristas, integradores y clientes oficiales;
3. Gartner / IDC / Forrester / Omdia / Canalys / Dell'Oro / Synergy / ISG públicos;
4. prensa especializada;
5. discovery, que nunca se convierte automáticamente en verdad ejecutiva.

Reglas:

- EMEA ≠ Iberia ≠ España ≠ Portugal;
- “no demostrado” ≠ “no existe”;
- una página antigua no pesa igual que una señal actual;
- partner directory ≠ capacidad probada;
- caso cliente/adjudicación/premio > mención comercial;
- no se reconstruyen contenidos licenciados de Gartner, Forrester o IDC.

## Archivos principales

- `data/base.json` — portfolio y solution plays;
- `data/vendor_intelligence.json` — baseline estratégico;
- `data/curated_evidence.json` — evidencia pública curada;
- `data/ecosystem.json` — integradores y referencias públicas;
- `data/research.latest.json` — grafo de inteligencia vivo;
- `data/research_status.json` — salud y ejecución;
- `data/changes.latest.json` — cambios detectados;
- `config/deep_research.json` — perfiles y presupuestos de investigación;
- `config/research_queries.json` — aliases, fuentes, queries, integradores, distribuidores y competitors;
- `config/source_registry.json` — jerarquía de fuentes;
- `config/strategy_engine.json` — motor de oportunidad, riesgo y ataque;
- `scripts/research.py` — colector y normalizador.

## Brave Search es opcional

La aplicación funciona y se autoactualiza sin Brave gracias a fuentes públicas sin clave. Si se configura `BRAVE_SEARCH_API_KEY`, la investigación semanal puede ampliar mucho la cobertura de web abierta y búsquedas `site:`.

Nunca se expone la clave en GitHub Pages: solo la usa GitHub Actions como `repository secret`.

## Actualizar desde VS Code

Si ya tienes el repositorio `estrategia` conectado:

```bash
git add .
git commit -m "Radar estrategico Westcon Iberia v1.4 Deep Intelligence"
git push
```

GitHub Pages seguirá usando la misma URL y los dos workflows empezarán a mantener la inteligencia automáticamente.

## Diseño

Se mantiene la estética ejecutiva de la presentación FY27: azul marino, blanco, Corbel/Arial y acentos naranja, magenta, turquesa y azul. **La complejidad pertenece al motor, no a la pantalla.**
