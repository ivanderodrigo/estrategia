# Cambios de Westcon Iberia Decision Intelligence v3.0

## Motor de investigación

- Ejecuciones con límite duro, reserva para publicación y señales de terminación.
- Supervisor con heartbeat, timeout exterior, fallback corto, validación y restauración del último dataset válido.
- Investigación por lotes, checkpoints y reanudación de pendientes.
- Circuit breaker por motor/dominio y cooldown exponencial.
- Aprendizaje adaptativo de autoridad, utilidad, latencia, precisión geográfica, corroboración y frescura.
- Exploración mínima para evitar que las fuentes conocidas oculten actores o temas nuevos.
- Publicación atómica de resultados parciales válidos.

## Política gratuita

- Eliminadas las dependencias de Brave Search y de la API tokenizada de BASE.
- Eliminadas las claves correspondientes de los workflows.
- Fuentes limitadas a endpoints, recursos descargables, RSS, sitemaps y páginas públicas sin suscripción.
- Gartner, IDC, Forrester y otras consultoras se utilizan solo mediante sus materiales públicos.
- Validación automática para impedir la reintroducción de esas claves.

## Fuentes y cobertura

- Universo semilla ampliado a 24 consultoras, 27 mayoristas y más de 55 integradores ES/PT.
- Descubrimiento dinámico con estado candidato y promoción únicamente tras corroboración independiente.
- Investigación entity-first además del análisis por fabricante.
- Contratación pública UE, España y Portugal integrada como señal trazable de demanda.
- Seguimiento explícito de linecards, certificaciones, partnerships, casos, clientes, cifras públicas y gaps.

## Interfaz

- Navegación responsiva con menú colapsable y redistribución por breakpoints.
- Vistas completas de fabricantes, mayoristas, integradores, tendencias, arquitecturas, sinergias/solapes, fuentes y operación.
- Filtros por país y búsqueda de entidades.
- Tabla de fabricantes con selección, orden y movimiento de columnas persistentes.
- Tooltips de contexto para métricas, confianza y procedencia.
- Panel operativo con resultado, run ID, etapas, salud por dominio y errores.

## Decisiones y exportación

- Gate exacto 100/100 con corroboración mínima para mostrar acciones.
- Hipótesis inferiores al umbral permanecen en investigación.
- PDF y PowerPoint con portada, metadatos de ejecución, selección de campos y aspecto ejecutivo.
- Las exportaciones aplican el mismo gate de acciones que la interfaz.

## Automatización y diagnóstico

- `scripts/configure_updates.py` configura zona horaria y horarios diario, semanal y mensual.
- Horarios UTC de verano/invierno generados automáticamente.
- `scripts/schedule_guard.py` evita el candidato DST incorrecto y ejecuciones duplicadas.
- Workflows sin reintento monolítico; todos conservan artefactos de diagnóstico.
- Nuevas pruebas deterministas de resiliencia y calendario.
