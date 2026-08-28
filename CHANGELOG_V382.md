# Changelog v3.8.2

- Corregido el modelo de Comstor: unidad Cisco de Westcon, nunca competidor.
- Eliminada la fila Comstor de Mayoristas competidores.
- Eliminadas menciones de Comstor como mayorista alternativo en fichas de fabricantes.
- Conservadas referencias Westcon-Comstor como fuente o contexto propio cuando son informativamente válidas.
- Añadido guardrail de generación `is_internal_westcon_distributor`.
- Reforzados tests y validador para impedir regresiones con `Westcon` o `Comstor`.
- Añadida explicación visible en la vista Mayoristas.
