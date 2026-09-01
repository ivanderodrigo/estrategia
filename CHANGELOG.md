# Changelog

## 4.0.2 — Typed Provenance + Non-Destructive Intelligence

- Preserva Tendencias, Arquitecturas y capacidades no relacionales de fabricantes ante ejecuciones posteriores.
- Reconstruye procedencia buscando evidencias exactas en snapshots históricos del repositorio Git.
- Trata documentación Westcon aportada como fuente primaria documental válida, aunque no tenga URL pública.
- Conserva datos sin origen reconstruido como `LEGACY_UNRESOLVED`; siguen visibles en rojo y mantienen el gap abierto.
- Client Intelligence aditivo: `Área Westcon` y `Fabricantes Westcon relacionados` sin borrar conocimiento anterior.
- Amplía investigación de clientes públicos/privados y descubrimiento conservador de sitios oficiales.
- Corrige migración/persistencia de `research_state` entre releases.

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
