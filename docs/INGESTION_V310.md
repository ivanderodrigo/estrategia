# Ingesta y aportaciones v3.10

## Qué puede hacer GitHub Pages por sí solo

GitHub Pages ejecuta HTML/CSS/JavaScript en el navegador, pero no dispone de un servidor propio que pueda escribir de forma segura en el repositorio. Por eso v3.10 separa dos modos:

### Modo local, sin infraestructura adicional
- Cualquier usuario puede pulsar **✎** en una etiqueta.
- La aportación se guarda en el navegador.
- Puede exportarse un JSON y añadirse a `inputs/manual/`.
- Un documento puede analizarse localmente y exportarse como JSON para `inputs/documents/`.

### Modo compartido
`config/v310/runtime.json` admite:

```json
{
  "shared_editing_enabled": true,
  "contribution_api_url": "https://tu-gateway.example/contributions",
  "document_api_url": "https://tu-gateway.example/documents"
}
```

El gateway debe autenticar al usuario y escribir en un repositorio mediante una GitHub App o credencial de servidor. **No pongas un PAT o secreto de GitHub dentro del JavaScript ni de `runtime.json`.**

## Contrato mínimo del gateway

### POST contribution_api_url
Recibe:

```json
{
  "version": "1",
  "contribution": {
    "section": "clients_private",
    "entity": "Empresa",
    "field": "technology_signals",
    "target_value": "Cloud",
    "note": "Contexto añadido por el usuario",
    "source_title": "Procedencia",
    "source_url": "",
    "source_date": "2026-08-28",
    "author": "AB"
  }
}
```

El servicio debería crear un JSON único en `inputs/manual/` de un repositorio privado o controlado.

### POST document_api_url
Recibe el paquete de texto/metadatos generado en el navegador. El servicio debería guardarlo en `inputs/documents/`.

## Repositorio privado de ingesta

Los workflows v3.10 pueden leer otro repositorio antes de investigar si existen los secrets:

- `PRIVATE_INPUT_REPO`: `owner/nombre-repo`
- `PRIVATE_INPUT_REPO_TOKEN`: token con **solo lectura** del repositorio privado de ingesta.

El contenido se clona durante el workflow, se escanea y **no se publica en GitHub Pages**.

## Formatos

- PPTX: texto de diapositivas y notas XML.
- DOCX: cuerpo, notas al pie y finales.
- PDF: extracción con `pypdf` en cron y PDF.js en navegador.
- TXT / MD / CSV / JSON / YAML: lectura directa.
- PPT binario antiguo: el navegador conserva metadatos, pero para extracción fiable conviene convertirlo a PPTX.

## Gobierno del dato

- Fuente pública y aporte interno nunca se fusionan silenciosamente.
- Una mención en un documento se muestra como **señal documental**, no como relación comercial confirmada.
- Las aportaciones manuales quedan marcadas como tales.
- El frontend público desplegado por `pages-deploy.yml` no incluye `inputs/`.
