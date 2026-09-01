# Arquitectura v4

## Contrato de diseño

La aplicación muestra una sola interfaz y oculta toda la complejidad operativa. El modelo interno separa hechos, señales e interpretaciones; ninguna señal débil se convierte automáticamente en relación comercial.

```mermaid
flowchart TD
    S["Fuentes públicas"] --> R["Research seguro"]
    R --> E["Evidencia candidata"]
    E --> V["Validación y procedencia"]
    V --> G["Grafo canónico"]
    G --> D["Datos internos"]
    D --> Q["Quality gate"]
    Q --> P["Proyección pública"]
    P --> U["Interfaz ejecutiva"]
```

## Capas

| Capa | Responsabilidad | Invariante |
|---|---|---|
| Dominio | normalización, aliases, campos y confianza | una entidad canónica por sección |
| Procedencia | limitar evidencia al dato que prueba | ninguna fuente vecina en un popup |
| Grafo | relaciones distribuye/integra/señal | una arista por par y tipo |
| Gaps | inventario estricto de deuda | una búsqueda vacía no cierra nada |
| Research | planificar, descubrir, extraer y aprender | HTTP 200 no es éxito de negocio |
| Persistencia | estado y publicación | escritura completa o rollback |
| Publicación | fragmentos aptos para navegador | `data/current` nunca llega a Pages |

## Ciclo de aprendizaje

Cada gap conserva intentos, evidencias aceptadas, fallos consecutivos y próxima fecha. El plan pondera sección, campo, criticidad, rendimiento observado y saturación. Los dominios conservan salud y abren circuito después de fallos repetidos; los éxitos relevantes aumentan su prioridad futura.

La cola de descubrimiento no promociona por sí sola un candidato externo. Una señal necesita evidencia suficiente y, cuando corresponde, corroboración independiente antes de incorporarse como hecho.

## Seguridad

- URLs absolutas HTTP(S), sin credenciales y solo puertos 80/443.
- Rechazo de localhost, IP privada, link-local, reservada, multicast y destinos DNS mixtos.
- Revalidación de la URL final tras redirecciones.
- Descarga en streaming con límite de bytes, timeout y reintentos acotados.
- El dataset público es una proyección, no una copia de la inteligencia interna.

## Consistencia

`atomic_write_many` prepara todos los ficheros antes de sustituirlos y restaura los anteriores si una publicación falla. `ProcessLock` impide ciclos locales simultáneos y GitHub Actions añade un mutex global. El publisher aborta si `main` ha avanzado desde el checkout, evitando sobrescribir investigación más reciente.
