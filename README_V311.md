# Westcon Iberia Decision Intelligence v3.1.1 hotfix

Corrige dos problemas detectados en el smoke test de v3.1:

1. `debt 47507` provenía de modelar la deuda como `entidad × dimensión × cada fuente del registro`. El registro de 151 fuentes es un catálogo de inteligencia, no 151 APIs independientes. v3.1.1 mide deuda por **gap entidad × dimensión**, por lo que el máximo queda en cientos, no decenas de miles.
2. `signals 0` ya no puede borrar inteligencia previa. El motor separa **proveedores de descubrimiento** (Google News RSS, GDELT y Brave opcional) de **fuentes objetivo** (fabricantes, integradores, mayoristas, oficiales, etc.), limita consultas por perfil y conserva el último dataset válido si una ejecución gratuita no devuelve señales.

También cambia el circuit breaker a nivel de proveedor, conserva historial de señales con deduplicación, añade métricas de cobertura y mantiene una ejecución `degraded` como no fatal para que la tarea diaria no se caiga si un proveedor gratuito falla.
