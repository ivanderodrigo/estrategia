# Westcon Iberia Business Intelligence v3.10.0

Production Candidate centrada en experiencia de uso, reporting ejecutivo y una nueva capa de inteligencia humana/documental.

## Cambios principales

### 1. Trazabilidad sin solapamientos
Los popovers de confianza/fuentes ya no viven dentro de la tabla con scroll. v3.10 utiliza un **portal global fijo** (`#tracePortal`) por encima de cabeceras, celdas sticky y barras de desplazamiento. Esto evita que una tarjeta de trazabilidad quede tapada por otras filas o columnas.

### 2. Cabecera reordenada
La navegación principal queda siempre visible y ordenada:

**Fabricantes · Mayoristas · Integradores · Clientes · Tendencias · Arquitecturas**

La parte derecha se sustituye por un botón **☰** de utilidades con:
- estado de datos,
- confianza,
- fuentes,
- aportaciones manuales,
- ingesta documental,
- informe/PPT,
- tamaño de texto.

En móvil/tablet la navegación pasa a una segunda línea horizontal desplazable y el menú de utilidades permanece accesible.

### 3. Informe PDF corregido y enriquecido
El PDF se renderiza en una superficie visible durante la captura de `html2canvas`, evitando el informe en blanco causado por el render fuera del viewport. Se añade una **Lectura ejecutiva** con KPIs, oportunidades públicas, cuentas privadas, momentum tecnológico y amplitud de ecosistema antes del detalle y las fuentes.

### 4. PowerPoint orientado a presentación
El PPT ya no empieza como una sucesión de fichas equivalentes a la web. Por defecto genera:
- portada,
- lectura ejecutiva,
- cuentas y ecosistema,
- una lectura ejecutiva por dominio,
- Trend Loop / Vendor Arena,
- metodología, confianza y gobernanza.

El usuario puede marcar **“Incluir anexo detallado”** para añadir todas las fichas y fuentes al final.

### 5. Aportaciones manuales
Cada etiqueta de las tablas incorpora **✎**. Las aportaciones:
- no sustituyen ni ocultan la evidencia pública;
- quedan diferenciadas como capa manual;
- se guardan en `localStorage` en modo GitHub Pages puro;
- pueden exportarse a JSON para `inputs/manual/`;
- pueden enviarse automáticamente si se configura un `contribution_api_url` seguro en `config/v310/runtime.json`.

### 6. Ingesta documental
Desde **☰ → Ingerir documento** se pueden analizar localmente:
- PPTX,
- DOCX,
- PDF,
- TXT / MD / CSV / JSON.

El navegador extrae texto y prepara un JSON de ingesta. El cron escanea:
- `inputs/manual/`
- `inputs/documents/`

y puede escanear también un **repositorio privado de ingesta** mediante los secrets `PRIVATE_INPUT_REPO` y `PRIVATE_INPUT_REPO_TOKEN`.

El motor identifica menciones directas a entidades del dataset y áreas tecnológicas, y las muestra como **señales documentales internas**, no como hechos públicos confirmados.

> No subas documentación confidencial a un repositorio público. Para inteligencia interna usa el repositorio privado de ingesta o un gateway autenticado.

## GitHub Pages y actualización automática

Se añade `.github/workflows/pages-deploy.yml`. Publica solo el sitio mínimo (`index.html`, `assets`, `data/v310` y `config/v310/runtime.json`) y **no publica `inputs/` ni los scripts internos**.

Para usarlo, GitHub → **Settings → Pages → Build and deployment → Source → GitHub Actions**.

La publicación se ejecuta:
- en pushes manuales relevantes a `main`, y
- al terminar correctamente los workflows diario, semanal o mensual.

## Validación

```powershell
$env:PYTHONPATH="scripts"
python scripts/v310/build_intelligence.py
python -m unittest tests/test_v310.py
python scripts/v310/validate_v310.py
node --check assets/v310/intelligence.js
node tests/ui_smoke_v310.js
```

## Rutas v3.10

- `assets/v310/` – frontend
- `data/v310/` – dataset publicado
- `scripts/v310/` – builder, pipeline, validador e ingesta
- `config/v310/` – runtime y nuevas fuentes
- `inputs/manual/` – contribuciones compartidas controladas
- `inputs/documents/` – documentos/paquetes que leerá el cron
