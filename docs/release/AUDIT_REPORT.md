# Auditoría técnica — v3.19.0

## KEEP

- `index.html`, `404.html`, `assets/app/`, `engine/`, `config/current/`, `data/current/`.
- Workflows `pages-deploy`, `research-daily`, `research-weekly`, `research-monthly`, `quality`.
- Fuente histórica útil únicamente cuando ha sido migrada a modelos canónicos y conserva evidencia.

## REMOVE

Se retiran del árbol activo, tras comprobar que el runtime y workflows no los referencian:

- `assets/vXXX`, `config/vXXX`, `data/vXXX`, `scripts/vXXX`;
- supervisores `research_supervisor_vXXX.py`;
- tests y aplicadores de generaciones antiguas;
- README/CHANGELOG versionados redundantes de raíz;
- snapshots `_baseline_v314` y `_baseline_v315` embebidos en el JSON de producción;
- outputs/cache/artefactos de investigación no necesarios en Pages.

La baseline extraída ocupaba ~379 MB; el árbol canónico final queda alrededor de 25 MB sin `.git`.

## CONSOLIDATE

- Cuatro tablas → un componente reusable.
- N generaciones de pipeline → `engine/` único.
- N datasets versionados → `data/current/`.
- Relaciones duplicadas por tabla/país → grafo canónico A–relación–B con scopes agregados.
- Planes de 48 pasos repetidos en cada gap → perfil de estrategia normalizado y generado bajo demanda.

## MIGRATE

- Inteligencia y relaciones válidas de v3.18 se migran una vez; el runtime v3.19 nunca lee `data/v318`.
- Arrow Electronics se resuelve a Arrow ECS; Digicomp a CloudIT; Soon queda asociado históricamente a NEXUS Solutions.

## REVIEW

- Facturación no corroborada por evidencia suficiente.
- Empleo cuando no hay perfil nominal o tecnología explícita.
- Seis line cards todavía sin suficiencia de evidencia.
- Integradores y Clientes mantienen la mayoría de sus gaps heredados: próxima prioridad de profundidad.
