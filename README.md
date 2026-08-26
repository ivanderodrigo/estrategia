# Westcon Iberia · Decision Intelligence v1.8

**España + Portugal · Solo inteligencia pública · GitHub Pages**

Aplicación estática para construir una estrategia tecnológica ejecutiva de Westcon Iberia con una regla de diseño: **hipersimple por fuera, extremadamente rigurosa por dentro**.

La interfaz conserva la organización visual del material FY27 y permite llegar a una decisión en segundos. El motor de fondo investiga, normaliza, cruza y pondera fabricantes, mercados, competidores, mayoristas, integradores, clientes públicos, contratación, consultoras, M&A, roadmap, recurrencia, partner programs, servicios, logística, financiación y señales regulatorias.

No utiliza revenue, margen, pipeline, CRM, objetivos, carga individual, personas ni otra información interna. El alcance es exclusivamente **información pública externa + portfolio/taxonomía derivados de la presentación FY27 facilitada**.

## Qué cambia en v1.8

### 1. Decision Intelligence, no receta genérica

El motor ya no recomienda automáticamente `Servicios + FLEX + 3D Labs`. Dispone de **47 palancas Westcon** y las puntúa contra el contexto concreto de cada fabricante. Una palanca solo aparece si supera su umbral de pertinencia.

Ejemplos de gates:

- **FLEX**: requiere encaje financiero, recurrencia/hardware y oportunidad suficiente;
- **3D Lab / PoC**: requiere necesidad real de prueba técnica o displacement;
- **Intelligent Demand / ABM**: se activa ante whitespace y necesidad de generación de demanda;
- **stock / staging**: exige intensidad hardware y complejidad de despliegue;
- **marketplace**: exige encaje cloud/SaaS o evidencia pública de marketplace;
- **managed services**: exige necesidad operativa/soporte, no solo que el vendor sea de seguridad;
- **lifecycle**: prioriza recurrencia, base instalada/referencias y expansión;
- **Tech Xpert / enablement**: prioriza gaps de capacidad o especialización del ecosistema;
- **GSCS / IoR / 3PL**: aparece cuando el patrón de proyecto exige escala multinacional o logística compleja.

Si ninguna acción de una función supera el umbral, el sistema muestra **“Sin acción prioritaria”** en lugar de consumir recursos por inercia.

### 2. Recomendaciones por 11 perfiles de Westcon

Cada fabricante genera una tesis central y recomendaciones distintas para:

1. Solution Architects / Preventa;
2. VSM — Vendor Success Manager;
3. PSM — Partner Success Manager;
4. Dirección VSM + Solution Architects;
5. Dirección PSM;
6. Country Manager;
7. Marketing;
8. Servicios / Soporte;
9. Operaciones;
10. Finanzas;
11. Logística.

Cada acción incluye:

- score contextual;
- motivos principales que la activan;
- evidencia relacionada;
- enlace a la fuente pública cuando existe;
- referencia a la capacidad oficial Westcon aplicable.

### 3. Catálogo de palancas Westcon mucho más amplio

El motor modela, entre otras:

**Preventa y tecnología**
- discovery y cualificación;
- arquitectura, sizing y BOM;
- RFI/RFP y defensa técnica;
- PoC/PoV;
- 3D Lab / Demo Lab / Tech Showcase;
- Tech Assessments;
- Tech Xpert / Tech ConneX;
- SkillBoost / Academy / educación;
- Tech Insights;
- arquitecturas de referencia y playbooks multivendor.

**Vendor management / negocio**
- joint business plan;
- priorización de casos de uso;
- especialización/certificación de partners;
- displacement competitivo;
- roadmap y executive alignment;
- category plan y gobierno de overlap.

**Partner Success**
- recruitment y activación de partners;
- segmentación por capacidad;
- capability maps;
- cross-sell multivendor;
- new-logo motions;
- lifecycle y expansión.

**Marketing**
- Intelligent Demand;
- campañas conjuntas con fabricante;
- ABM;
- playbooks verticales;
- Tech Insights, webinars y eventos.

**Servicios y soporte**
- diseño profesional;
- instalación, migración y upgrades;
- health checks / assessments;
- Westcon Care / Assist;
- Managed Services;
- Engineer-to-Site.

**Operaciones, logística y supply chain**
- planificación de stock y disponibilidad;
- staging;
- IoR / 3PL / logística avanzada;
- reverse logistics;
- GSCS;
- PartnerCentral / lifecycle operations.

**Finanzas y consumo**
- FLEX;
- CAPEX → OPEX;
- estructura de suscripción/deal;
- cloud marketplaces / private offers.

### 4. Tesis estratégicas por fabricante

El motor clasifica el contexto en arquetipos como:

- `SCALE PLATFORM`
- `BUILD ECOSYSTEM`
- `DEFEND CHANNEL`
- `DISPLACE`
- `CROSS-SELL`
- `PUBLIC SECTOR`
- `HARDWARE SCALE`
- `RECURRING EXPANSION`
- `GOVERN OVERLAP`
- `INVESTIGATE`

Dos vendors con un score parecido pueden recibir recomendaciones diferentes si difieren en canal, ecosistema, fiabilidad, recurrencia, hardware, M&A, demanda pública o presión competitiva.

## Motor v8: 14 dimensiones + riesgo + incertidumbre

El análisis combina, entre otras señales:

- momentum del mercado;
- portfolio fit;
- recurrencia;
- diferenciación;
- sinergias;
- señal pública de consultoras;
- leverage de servicios;
- fortaleza de ecosistema;
- prueba de cliente;
- capacidad de integradores;
- cobertura España/Portugal;
- demanda pública;
- prueba competitiva;
- confianza de evidencia.

A ello se suman variables derivadas como:

- momentum del fabricante;
- intensidad hardware/cloud;
- complejidad técnica;
- necesidad de PoC;
- encaje regulatorio;
- marketplace fit;
- finance fit;
- deployment complexity;
- support need;
- managed-service fit;
- stock need;
- lifecycle fit;
- demand-generation need;
- partner-enablement need;
- M&A disruption;
- shared ecosystem;
- diversidad vertical;
- potencial de deal y opcionalidad estratégica.

### Riesgo

Se calcula aparte y contempla:

- overlap interno;
- presión de otros mayoristas;
- intensidad de fabricantes competidores;
- concentración de integradores/clientes;
- gaps de evidencia;
- antigüedad;
- desequilibrio ES/PT;
- debilidad de ecosistema;
- concentración de contratación;
- falta de prueba competitiva.

### Incertidumbre y estabilidad

No se muestra falsa precisión. Si la evidencia es pobre, el score se contrae hacia una posición neutral. Además, el motor ejecuta una prueba de sensibilidad/estabilidad: una decisión que cambia demasiado ante pequeñas perturbaciones se degrada a una postura más prudente.

## Evidencia a la vista

Al seleccionar un fabricante se puede abrir `Ver datos` para visualizar:

- drivers y frenos;
- scores;
- mayoristas ES/PT;
- integradores;
- clientes públicos;
- señales de Gartner / IDC / Forrester / Omdia / Canalys / Dell'Oro / Synergy / ISG;
- contratación pública;
- sinergias;
- overlap;
- evidencias concretas;
- por qué se activa cada recomendación por perfil.

La interfaz distingue siempre **hecho público**, **señal de mercado** e **inferencia estratégica propia**.

## Investigación de fondo

### Velocidad 1 · diaria

`.github/workflows/research-daily.yml`

Busca cambios rápidos:

- distribución;
- nuevos partners/integradores;
- clientes/casos;
- M&A;
- producto;
- partner program;
- customer stories;
- noticias de canal;
- señales competitivas recientes.

### Velocidad 2 · semanal profunda

`.github/workflows/research-weekly.yml`

Recalibra el landscape con:

- búsqueda abierta;
- webs y sitemaps oficiales;
- canal e integradores;
- customer stories;
- consultoras;
- TED;
- contratación ES/PT;
- comparativas vendor-vendor;
- displacement/migration;
- datos de mercado;
- gaps de cobertura.

### Velocidad 3 · mensual exhaustiva

`.github/workflows/research-monthly.yml`

Barrido long-tail e histórico con presupuestos mucho mayores. Añade especialmente:

- investor relations / annual reports / filings públicos;
- ARR, subscription growth y software mix cuando son públicos;
- R&D / roadmap / platformization;
- end-of-sale/end-of-support;
- partner tiers y especializaciones;
- certified partners;
- customer counts/references;
- competitive wins/migrations;
- MSSP programs;
- marketplaces;
- stock/staging/servicios/lifecycle;
- Common Crawl como discovery + revalidación;
- Arquivo.pt para histórico;
- contratación pública extensa;
- señales de cambio estructural.

El planificador no reparte búsquedas por igual: dedica más presupuesto a **gaps concretos** de un vendor/país/dimensión y mantiene fair-share para impedir que una sola marca absorba todo el esfuerzo.

## Fuentes utilizadas

### Primarias
- fabricantes;
- Westcon/Comstor/Datatec públicos;
- mayoristas;
- integradores;
- clientes;
- investor relations;
- reguladores/open data;
- TED;
- PLACSP / datos abiertos de contratación en España;
- dados.gov.pt / Portal BASE / IMPIC en Portugal.

### Analistas públicos
- Gartner;
- IDC;
- Forrester;
- Omdia;
- Canalys;
- Dell'Oro;
- Synergy Research;
- ISG;
- KuppingerCole;
- Everest Group;
- GigaOm.

Solo se utiliza contenido públicamente accesible. **No se reconstruyen Magic Quadrants, Waves, MarketScapes ni contenidos licenciados.**

### Discovery
- Brave Search API (opcional);
- Google News RSS;
- GDELT;
- Arquivo.pt;
- Common Crawl.

Discovery no equivale a evidencia ejecutiva: la señal se revalida y se vuelve a puntuar.

## Modelo de calidad de evidencia

Cada evidencia se pondera por:

- autoridad;
- frescura;
- precisión geográfica;
- relación directa;
- corroboración;
- diversidad de fuentes;
- especificidad.

Reglas esenciales:

- EMEA ≠ Iberia ≠ España ≠ Portugal;
- ausencia pública ≠ inexistencia;
- partner directory ≠ capacidad demostrada;
- adjudicación / caso / premio / certificación pesa más que una mención;
- contratación tecnológica sin vendor explícito = demanda de mercado, no cliente del vendor;
- una relación de canal antigua no se mantiene activa indefinidamente;
- las contradicciones se conservan como conflicto a validar.

## Contexto competitivo Iberia modelado

- **Juniper Networks** no se cuenta como vendor activo del scope Iberia; permanece monitorizado como competidor estratégico.
- **Extreme Networks** incluye a **TD SYNNEX España** como presión de canal pública.

El motor usa la competencia de canal para decidir **cómo diferenciar Westcon**, no para reducir automáticamente el atractivo del fabricante.

## Accesibilidad y simplicidad

La cabecera incorpora:

- `A−` para reducir texto;
- `A+` para aumentar texto;
- `Ver datos` para abrir/cerrar profundidad;
- `Informe / PPT` para exportación modular.

El tamaño elegido se conserva en el navegador.

## Informes y presentaciones modulares

Al pulsar `Informe / PPT` se pueden seleccionar módulos:

- ejecutivo;
- portfolio;
- recomendaciones por perfiles;
- canal/competencia;
- analistas;
- ecosistema;
- sinergias;
- tendencias;
- evidencias;
- metodología.

La aplicación genera:

- **PDF ejecutivo**;
- **PowerPoint editable**.

No hay que exportarlo todo: se construye únicamente con los módulos marcados.

## Arquitectura

```text
Internet / Open Data / Analyst Public Content
                    ↓
             GitHub Actions
        diaria · semanal · mensual
                    ↓
 discover → normalize → dedupe → corroborate
                    ↓
          Evidence / Relationship Graph
                    ↓
  vendor ↔ market ↔ competitor ↔ distributor
    ↕        ↕          ↕            ↕
 analyst ↔ integrator ↔ customer ↔ procurement
                    ↓
          Decision Intelligence v6
                    ↓
         47 palancas × 11 perfiles
                    ↓
             GitHub Pages UI
                    ↓
          PDF / PowerPoint modular
```

## Calidad antes de auto-publicar

Todos los workflows ejecutan `scripts/validate.py` antes de hacer commit. Se valida:

- JSON;
- alineación de vendors;
- Juniper fuera de activos;
- TD SYNNEX España en Extreme;
- weights del motor;
- taxonomía de contratación;
- geografía;
- URLs en evidencia fuerte;
- Decision Intelligence config;
- roles/acciones/gates;
- workflows diaria/semanal/mensual;
- ausencia de campos internos prohibidos.

Si falla la validación, el dataset nuevo **no se publica**.

## APIs / secretos

Ninguno es obligatorio para visualizar la aplicación.

### Opcional · Brave Search

`BRAVE_SEARCH_API_KEY`

Aumenta mucho el long-tail de búsqueda abierta.

### Opcional · Portal BASE Portugal

`BASE_API_TOKEN`

Añade enriquecimiento REST a las fuentes portuguesas públicas ya procesadas.

Las claves viven únicamente como GitHub Actions Secrets y nunca se exponen en GitHub Pages.

## Instalación / actualización desde VS Code

Si el repositorio `estrategia` ya está conectado a GitHub, sustituye los archivos conservando `.git/` y ejecuta:

```bash
git add .
git commit -m "Westcon Iberia Decision Intelligence v1.8"
git push
```

GitHub Pages conserva la URL. Los workflows periódicos seguirán actualizando los datasets.

## Principio de producto

> **La complejidad pertenece al motor, no a la pantalla.**

La meta de v1.8 es que Dirección pueda entender el qué en segundos, mientras cualquier recomendación pueda defenderse abriendo el porqué, los datos y las fuentes.

## Motor de capacidades Westcon v1.8

La recomendación ya no parte solo del mercado: primero valida **qué capacidades Westcon existen y cuáles aplican de verdad a cada fabricante**. El fichero `config/capability_intelligence.json` separa capacidad local, EMEA y global; distingue evidencia pública, documentación facilitada, confirmación del proyecto y simples hipótesis; y bloquea una recomendación cuando la compatibilidad no está demostrada.

Se han incorporado como fuentes de referencia el documento **Tech Insights Lead to Opportunity**, que identifica 12 categorías, 10 vendors y 22 assessments, y el documento **3D Lab**, que identifica 17 technology vendors, 27+ use cases y más de 2.450 usuarios FY25. La matriz de 3D Lab solo habilita vendors que aparecen expresamente en esa cobertura; UiPath, por ejemplo, no queda habilitado para 3D Lab.

El motor investiga periódicamente `fabricante × capacidad Westcon × país × evidencia`, además de mercado, analistas, canal, integradores, clientes, licitaciones y competencia. Una señal de discovery no puede promocionarse a capacidad verificada sin evidencia oficial o corroboración suficiente.

## v1.8.1 — hotfix del motor de investigación

- Corrige el `NameError: clamp is not defined` que podía hacer fallar los perfiles diario, semanal y mensual al agregar demanda de contratación pública.
- Añade `scripts/selftest.py`, un preflight offline que prueba las funciones de agregación antes de iniciar las búsquedas largas.
- Los tres workflows ejecutan ahora `py_compile` + self-test antes del crawl, evitando descubrir errores deterministas al final de una ejecución de muchos minutos.
- Actualiza `actions/checkout` y `actions/setup-python` a runtimes Node 24 para eliminar los avisos de deprecación de Node 20 en runners hospedados actuales.
