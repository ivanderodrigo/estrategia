# Auditoría técnica v3.18.0

## KEEP
- Runtime activo v317 como baseline funcional de compatibilidad mientras v318 lo envuelve.
- Datos históricos v31–v317: contienen evidencia y snapshots que todavía alimentan procesos y sirven de trazabilidad.
- Supervisores heredados referenciados por la cadena de investigación.

## REMOVE
- `__pycache__` y `.pyc`: basura regenerable. Eliminados antes de empaquetar.
- No se eliminó ningún dataset/versionado solo por antigüedad.

## CONSOLIDATE
- Infraestructura de tablas: consolidada en un único motor v318.
- Relaciones Fabricante/Mayorista/Integrador: nueva fuente canónica `relationship_graph.json`.
- Aliases de entidades: centralizados en `config/v318/entity_aliases.json`.

## MIGRATE
- Los supervisores v31–v317 siguen siendo capas de compatibilidad/foundation. La siguiente consolidación debería migrar la investigación heredada a un supervisor único sin perder evidencia.
- Los datasets históricos voluminosos deberían pasar a almacenamiento histórico/artefactos si dejan de ser dependencia de runtime.

## REVIEW
- Repositorio ~300 MB principalmente por snapshots históricos `data/v313..v317`.
- Varios README/CHANGELOG históricos son documentación, no runtime.
- Los tests de versiones antiguas están conservados; no deben ejecutarse como suite de versión activa porque validan `VERSION` histórico.
- Revisar progresivamente CSS/JS de versiones antiguas cuando la migración a v318 sea estable.

## Workflows
- Se actualizaron daily/weekly/monthly/pages a v318.
- Se añadió auditor automático de rutas ejecutables y validadores.
- No se detectan referencias v318 a scripts inexistentes tras la corrección.
