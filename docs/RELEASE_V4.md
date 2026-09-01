# Auditoría y entrega v4.0.0

## Resultado

- Quality gate: **100/100**, sin errores ni warnings.
- 409 entidades, 1.132 fuentes registradas y 388 dominios.
- 1.243 evidencias válidas y 1.220 relaciones canónicas con procedencia.
- 3.369 campos poblados y trazables.
- 1.823 gaps reales conservados; 718 son decisionales.
- 80 oportunidades TED vigentes cargadas en el ensayo operativo, filtradas por CPV IT.

El total de gaps aumenta frente a v3.20 por dos motivos medibles: la auditoría ha dejado de considerar trazables 124 campos que heredaban evidencia de otros elementos y ha rechazado 31 aristas sin soporte atómico suficiente; además, el ensayo del conector TED incorporó 77 entidades netas nuevas, cuyos campos aún pendientes se añaden honestamente al inventario. No es pérdida de inteligencia: es deuda antes oculta más crecimiento real. La antigua cifra de gaps críticos también era incorrecta porque trataba casi todo campo vacío como crítico; v4 usa el atributo de decisión del esquema.

## Hallazgos corregidos

| Hallazgo | Corrección |
|---|---|
| Runner que sondeaba rutas pero no ejecutaba las consultas previstas | cascada real de fuentes, extracción, aceptación y aprendizaje |
| 1.398 gaps reconstruidos siempre con cero intentos | memoria persistente por gap y fecha de reintento |
| Evidencia de un campo copiada a todos sus valores | procedencia atómica y preferencia por afirmación exacta |
| Scheduler guard inerte | workflows reales diaria/semanal/mensual sobre runner común |
| Publicación y JSON expuestos a escrituras parciales | transacción, rollback y lock |
| Red sin defensa integral frente a SSRF/redirecciones | guardia de destino antes y después del fetch |
| Workflows y tests con versiones incrustadas | versión canónica y pruebas de invariantes |
| Documentación repetida y contradictoria | tres documentos vigentes |
| Cabecera de tabla no permanecía fija | sticky header con contexto de apilado coordinado |

## Pruebas de regresión

La suite cubre clasificación de negocio, duplicados, aristas, procedencia de cada relación visible, caso exacto 1Password/Ingram, gaps persistentes, aislamiento de datos públicos, SSRF, circuit breaker, TED, escritura transaccional, encoding Windows, workflows y smoke UI. Además se ejecutan compilación Python, auditoría de seguridad, validación YAML, sintaxis JavaScript y `git diff --check`.

## Deuda honesta

Los 1.823 gaps no se rellenan con inferencias opacas. El motor los recorre de forma acumulativa y conserva cada intento. Las webs protegidas por WAF, contenido exclusivamente JavaScript o fuentes no públicas pueden seguir requiriendo corroboración alternativa o aportación humana; esa limitación se muestra como gap, nunca como hecho inventado.
