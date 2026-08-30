# Auditoría de calidad v3.15

## Problemas detectados en v3.14

- Las columnas opcionales poco pobladas podían quedar ocultas.
- Los vacíos opcionales se mostraban con un guion, de modo que no se distinguían de un campo no aplicable.
- La métrica principal solo incluía un subconjunto de campos decisionales.
- La confianza del dato no estaba separada de la interpretación comercial ni del riesgo de actuar.
- Había evidencias históricas sin fecha o descripción explícita.

## Correcciones verificadas

- Todos los campos declarados cuentan y permanecen visibles.
- `Por investigar` es el único fallback de un valor previsto sin evidencia suficiente.
- Cada gap tiene 15 estrategias y una regla que impide cerrarlo por cero resultados.
- Las nuevas señales de empleo y las interpretaciones comerciales están etiquetadas.
- Las fuentes Peer Insights y G2 no se presentan como oficiales.
- Comstor no aparece como mayorista competidor y las listas de fabricantes/mayoristas son disjuntas.

## Lectura honesta de la mejora

La reducción total de gaps combina dos efectos: 44 campos realmente poblados con investigación nueva y la reparación de trazabilidad en evidencia ya existente. No se han eliminado entidades, campos ni columnas. Aún quedan 1.968 tareas abiertas y deben seguir investigándose en los ciclos programados.
