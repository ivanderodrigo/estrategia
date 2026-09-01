# v4.0.1 — Client Evidence Hardening

- Ningún dato sustantivo sin URL pública vinculada se publica como claim interactivo.
- Listas simples exigen evidencia atómica por elemento; lo no sustentado vuelve a `Por investigar`.
- Clientes públicos y privados ganan `Área Westcon` y mapeo de fabricantes Westcon sustentado por evidencia.
- Mayor prioridad de investigación para clientes, más rutas tecnológicas y descubrimiento conservador de web oficial.
- Se corrige la normalización que podía vaciar evidencias explícitas en listas no relacionales.

# Changelog

## 4.0.0 — reconstrucción canónica

### Núcleo

- Versión única leída desde `VERSION`; eliminadas constantes y referencias de continuidad duplicadas.
- Persistencia JSON atómica y publicación transaccional de datos internos y públicos.
- Lock interproceso compatible con Linux, macOS y Windows.
- Grafo canónico de evidencia con proyección bidireccional y aristas deduplicadas.
- Política de procedencia común para migración, grafo, controles de calidad y UI.

### Investigación autónoma

- Planificación adaptativa por prioridad, tipo de gap, rendimiento histórico y fecha de siguiente intento.
- Estado persistente por gap y por dominio, backoff exponencial, circuit breaker y cola de descubrimiento acotada.
- Cascada de rutas oficiales y extracción conservadora con fragmento, términos coincidentes y digest del contenido.
- Conector estructurado a TED para nuevas oportunidades públicas ES/PT.
- Supervisor con heartbeat, presupuesto de tiempo, terminación de árbol de procesos, fallback y diagnóstico durable.
- Workflows diaria, semanal y mensual sobre un runner común, mutex global, tests antes/después y publicación protegida frente a snapshots obsoletos.

### Seguridad y calidad

- Protección SSRF previa y posterior a redirecciones, DNS público, puertos estándar y tamaño máximo de respuesta.
- Auditoría local de secretos y patrones inseguros; Dependabot para Python y GitHub Actions.
- Quality gate de trazabilidad atómica: una relación sin fuente específica no se muestra como confirmada.
- Los gaps se conservan aunque una búsqueda no produzca resultados; los intentos ya no se reinician al reconstruir.

### Interfaz

- Cabecera completa y columna Entidad fijas en tablas con desplazamiento vertical/horizontal.
- El popup de un elemento de lista usa coincidencia exacta; se elimina el fallback por posición o por campo completo.
- `1Password → Ingram Micro` muestra únicamente la evidencia de esa relación.

### Limpieza

- Eliminados el guard programado inerte, tests con versión incrustada, cachés Python y documentación de releases contradictorias.
- Conservado un solo conjunto de documentación operativa y arquitectónica.
