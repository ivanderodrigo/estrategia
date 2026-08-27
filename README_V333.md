# Westcon Iberia Decision Intelligence v3.3.3

## Objetivo
Versión de estabilización del modelo de datos antes del salto a Work/v3.4. No añade funcionalidad superficial: corrige identidad, consolidación, tiering y métricas comparables.

## Cambios clave
- Sustituye el ambiguo “duplicados exactos consolidados” por **variantes de fuente/operación consolidadas**.
- Genera `data/v33/deduplication_report.json` con todas las consolidaciones y los ámbitos preservados.
- Conserva `scope_variants`, `operations`, `operation_count`, `canonical_name` y `canonical_group` en cada perfil.
- El scheduler trabaja sobre entidades canónicas, evitando repetir consultas por filas duplicadas de v3.1.
- `T1/T2/T3` pasa a ser un tier **relativo de importancia estructural**, separado de confianza y cobertura.
- Añade `strategic_importance_score` y mantiene confianza/cobertura como métricas independientes.
- Coverage separa `difference_between_averages` de `average_knowledge_debt`.
- Genera `data/v33/relationship_movement.json` para medir transiciones de relaciones entre ejecuciones comparables.
- UI: nueva columna opcional “Importancia estratégica relativa” y explicaciones más claras de tier, confianza y deuda de conocimiento.

## Instalación
Copiar el contenido encima del repositorio y ejecutar:

```powershell
python tools/aplicar_v333.py
Get-Content VERSION
python tests/test_v333_unittest.py
node --check assets/v333/ecosystem-intelligence.js
python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32
```

`VERSION` debe devolver `3.3.3`.

## Nuevos datasets de auditoría
- `data/v33/deduplication_report.json`
- `data/v33/relationship_movement.json`

## Lectura recomendada de la salida
La línea final distingue:
- perfiles canónicos;
- variantes de fuente consolidadas y grupos afectados;
- distribución T1/T2/T3;
- cobertura media;
- diferencia entre medias;
- deuda media de conocimiento;
- evidencias nuevas/acumuladas;
- cambios de estado de relaciones y casos cuya incertidumbre se resolvió.
