## 4.1.0 — Business Intelligence Analysis & Accrediting Sources

- La UI solo presenta evidencia pública actual y documentación oficial Westcon aportada; H/archivo/linaje quedan internos.
- Unificación documental por identidad + slide y coexistencia Westcon/pública en un mismo claim.
- Discovery-only deja de poder acreditar un dato o cerrar un gap.
- Esquemas BI aditivos y tipados para fabricantes, integradores, mayoristas y clientes.
- Selector de columnas profesional con búsqueda, estados accesibles, esenciales, reset y persistencia.
- Constructor de filtros genérico con AND/OR, grupos, operadores tipados, guardado, URL state y contador inmediato.
- Informes construidos sobre el subconjunto exacto en imprimible/PDF, CSV y PowerPoint.
- Confianza explicable por calidad, actualidad, evidencia primaria, corroboración y contradicciones.
- Investigación pública ampliada y prioridad específica para claims conservados con solo linaje histórico.
- Gate de preservación para entidades, valores, evidencia, relaciones, tendencias, arquitecturas, fabricantes y capacidades documentadas.
- 76 tests Python más smoke UI y test Node de filtros/informes.

## 4.0.6 — Evidence Preservation & Public Verification

- Ningún dato existente se elimina por falta de URL.
- WESTCON_DOCUMENT (A1) o una fuente pública actual sustentan el dato.
- Si falta A1, el dato se conserva y entra en investigación pública.
- H, curación e inferencia se mantienen como linaje/contexto.
- La investigación busca sostener el mismo dato, no sustituirlo automáticamente.

## 4.0.5 — Source Intelligence Rationalization

- Racionaliza fuentes en A1, A2, B, C y H.
- Ninguna H cierra por sí sola un gap.
- Toda H sin fuente abierta actual genera revalidación persistente.
- Re-fetch de URLs históricas y ampliación a web oficial/catálogo.
- Match atómico de valor para no adjudicar fuentes genéricas a items.
- La presentación FY27 permanece como A1 y coexiste con investigación externa.
- La UI separa fuentes actuales de histórico/linaje.

## 4.0.4 — Document Provenance Repair

- Corrige la regresión que ocultaba la presentación corporativa Westcon cuando un campo ya tenía evidencia pública.
- Las capacidades de fabricante conservan trazabilidad `WESTCON_DOCUMENT` a nivel de campo y de cada capacidad individual.
- La evidencia documental Westcon es aditiva: nunca sustituye ni elimina una fuente pública existente.
- La UI muestra tipo documental, nombre del fichero, slide, procedencia y dato atómico aunque no exista URL pública.
- Nuevos tests impiden que una futura normalización vuelva a separar las capacidades de su documento Westcon.

## 4.0.3 — Provenance Archaeology

- Reconstrucción aditiva de fuentes desde ZIPs históricos locales del proyecto.
- Coincidencia conservadora entidad + campo + valor/item exacto; nunca importa valores antiguos.
- Registro persistente `archive_provenance_registry.json` para reutilizar la arqueología en GitHub Actions.
- Lineage por dato: primera aparición, última versión con evidencia atómica y versiones de recuperación.
- Clasificación de evidencias UNKNOWN mediante antiguos Source Intelligence Registries cuando coincide la URL exacta.
- PPTX históricos se usan solo como corroboración contextual y nunca cierran gaps.
- Knowledge Guard v4.0.2 permanece activo: Tendencias, Arquitecturas y capacidades de fabricantes no pueden degradarse silenciosamente.

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
