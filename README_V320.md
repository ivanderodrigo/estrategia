# Westcon Iberia Decision Intelligence v3.2.0

v3.2 cambia la unidad de conocimiento: **una noticia ya no es un hecho**. El pipeline conserva v3.1.5 como motor rápido de discovery y añade una capa de Evidence & Event Intelligence que transforma artículos y fuentes directas en eventos, relaciones, materialidad y decisiones explicables.

## Arquitectura

`fuentes → candidatos → event extraction → alcance geográfico → clustering/corroboración → confidence + materiality + Westcon relevance → knowledge graph → decisiones`

### 1. Evidence fabric multifuente

El registro v3.1 mantiene 151 fuentes. v3.2 las convierte en un universo operativo con dos vías y un bucle de aprendizaje que premia autoridad, fiabilidad, novedad y rendimiento real de materialidad:

- conectores directos de alta autoridad para fuentes estructuradas;
- acceso directo progresivo a RSS/Atom de las fuentes del registro, con rotación y caché de feeds;
- v3.1.5/Google News queda como discovery transversal y fallback, no como fuente única de verdad.

Conectores directos incluidos en 3.2.0:

- **TED Search API v3** (contratación pública UE, keyless);
- **PLACSP Atom oficial** (contratación pública española, con degradación limpia si el WAF bloquea el runner);
- **CISA KEV** (explotación activa de vulnerabilidades);
- **FIRST EPSS** (weekly/monthly, enriquecimiento de CVE);
- **NVD 2.0** (weekly/monthly, vulnerabilidades);
- **SEC EDGAR** (weekly/monthly, resolución pública de CIK y filings 8-K/10-Q/10-K/20-F/6-K);
- **Portal BASE API** queda registrado explícitamente como `token_required`: el portal es público, pero su API REST de extracción masiva exige registro/autorización IMPIC, por lo que no se finge acceso automático;
- **generic RSS/Atom direct feed rotation** sobre el catálogo de 151 fuentes.

No se requiere ninguna librería Python adicional: usa stdlib y sigue siendo compatible con GitHub Actions/Pages.

### 2. Taxonomía de eventos

v3.2 separa hechos de interpretación competitiva. `competitive` deja de ser cajón de sastre. Tipos principales:

- distribution_agreement
- partnership
- customer_reference
- procurement_award
- certification
- award
- ma_acquisition / investment
- leadership_change / hiring
- product_release / service_launch / managed_service
- capability_expansion / market_expansion
- analyst_positioning
- financial_performance / strategy
- operational_incident / security_incident
- pricing_licensing / end_of_sale
- channel_program / technology_trend / regulatory_change

Incluye protecciones específicas frente a los errores encontrados durante la auditoría v3.1: buy-rating ≠ M&A; award ≠ procurement; certificación de estudiantes ≠ certificación del integrador; OTHER_REGION reduce drásticamente relevancia Iberia; earnings preview se considera bajo valor.

### 3. Clustering y corroboración

Copias/sindicaciones del mismo hecho se agrupan. El resultado conserva fuentes y URLs corroborantes, y la corroboración aumenta confianza en vez de inflar el contador de eventos.

### 4. Tres scores independientes

- **confidence**: qué tan defendible es el hecho;
- **materiality**: cuánto puede importar al negocio;
- **westcon_relevance**: cuánto importa específicamente a Westcon Iberia.

Una noticia puede ser cierta pero irrelevante. Ejemplo: una licitación Cisco en Costa Rica se conserva como contexto si procede, pero queda penalizada como `OTHER_REGION` y no debe subir al panel ejecutivo por defecto.

### 5. Knowledge Graph

`data/v32/knowledge_graph.json` crea nodos y relaciones persistentes a partir de eventos: DISTRIBUTED_BY, PARTNERS_WITH, CUSTOMER_RELATION, PROCUREMENT_INVOLVEMENT, ACQUIRED_OR_MERGED, etc.

### 6. Decision Engine

`data/v32/decisions.json` solo eleva eventos que superan umbrales de materialidad, confianza y relevancia. Cada decisión conserva el porqué, acción recomendada, fuentes, contraevidencia y trigger de cambio.

## Salidas

- `data/v32/direct_signals.json`
- `data/v32/events.json`
- `data/v32/knowledge_graph.json`
- `data/v32/decisions.json`
- `data/v32/briefing.json`
- `data/v32/source_health.json`
- `data/v32/source_coverage.json`
- `data/v32/source_learning.json`
- `data/v32/research_priorities.json`
- `data/v32/last_run.json`

El frontend añade **Decision Intelligence** al selector existente y muestra KPIs, oportunidades, amenazas, decisiones prioritarias y eventos de alta materialidad.

## Instalación

Desde la raíz del repo con `.venv` activado:

```powershell
python tools/aplicar_v320.py
Get-Content VERSION
python tests/test_v320_unittest.py
```

Debe mostrar `3.2.0` y los tests deben terminar en `OK`.

Primera prueba usando los datos v3.1.5 existentes, sin lanzar otra investigación v3.1:

```powershell
python scripts/research_supervisor_v32.py --profile daily --max-runtime 180 --skip-v31
```

Prueba integral antes de push:

```powershell
python scripts/research_supervisor_v32.py --profile daily --max-runtime 720
```

El instalador cambia automáticamente los workflows que ya apuntaban a `research_supervisor_v31.py` para que utilicen `research_supervisor_v32.py`.

## Filosofía de seguridad de decisión

- ausencia pública ≠ inexistencia;
- una noticia ≠ un hecho;
- una fuente secundaria no desplaza una primaria;
- una señal verdadera puede no ser material;
- un evento global puede no ser relevante para Iberia;
- una recomendación fuerte exige confianza y materialidad suficientes;
- fallos de una fuente gratuita degradan cobertura, nunca destruyen el último dataset válido.
