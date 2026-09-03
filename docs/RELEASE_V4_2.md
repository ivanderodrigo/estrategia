# Westcon Iberia Decision Intelligence v4.2.0

## Research Intelligence & Scalable Data

v4.2.0 parte de la baseline estable `c2b1e54` (v4.1.0 + deep + HF11) y mantiene sus invariantes de preservación y evidencia pública.

### 1. Almacenamiento interno escalable

`data/current/intelligence.json` deja de ser un monolito cercano al límite de GitHub. Se convierte en un puntero de compatibilidad de pocos bytes y el dataset canónico se almacena en `data/current/intelligence_store/` mediante shards JSON deterministas y acotados.

El cambio es transparente para el código existente: `engine.storage.read_json()` y `atomic_write_json()` siguen siendo la interfaz habitual. El pipeline publica shards directamente y el research checkpoint escribe el mismo formato.

Invariantes:

- round-trip semántico exacto del dataset;
- manifest con SHA-256 por shard y hash semántico global;
- objetivo de shard de 8 MiB;
- release gate a 25 MiB por shard;
- no Git LFS;
- el frontend continúa consumiendo exclusivamente `data/public/`.

### 2. Gap Intelligence

Cada gap abierto incorpora ahora:

- `business_value_score`;
- `researchability_score`;
- `priority_score`;
- `priority_tier` P0–P3;
- `source_family`;
- `source_strategy` con familias, tipos de fuente, razón y query hints;
- `priority_reason` explicable.

El KPI nuevo `business_weighted_coverage_pct` evita interpretar el número bruto de gaps como calidad. Tener más entidades puede aumentar los gaps y, simultáneamente, aumentar mucho la inteligencia disponible.

### 3. Planner con fairness

El planner mantiene aprendizaje por rendimiento histórico pero incorpora:

- prioridad de negocio del gap;
- boost para `Pendiente de validación pública`;
- target values y revalidation seeds;
- source playbook por campo;
- penalización progresiva por no-yield;
- cuotas de primera pasada por sección para que clientes públicos no monopolicen un run acotado.

Las cuotas son de fairness, no hard caps: si otras secciones no tienen trabajo suficiente, la segunda pasada usa la capacidad restante.

### 4. Fuentes

Se amplían rutas oficiales para partner locators, line cards, alianzas, managed services, case studies, careers, investor relations, procurement/tenders y technology/architecture pages.

PPT, portfolio e histórico siguen siendo memoria de investigación. Nunca vuelven a ser evidencia acreditativa visible.
