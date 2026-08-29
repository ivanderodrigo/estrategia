# Westcon Iberia Business Intelligence · v3.12.0

## Business intelligence

- **Mayoristas positive-validation-first**: una entidad solo puede entrar en `Mayoristas` si una fuente fiable la identifica explícitamente como distribuidor/mayorista/VAD. Se excluyen fabricantes y proveedores aunque aparezcan en páginas de canal, empleo, casos o ecosistemas.
- Universo semilla ampliado con rankings/directorios de canal de España y Portugal, preservando evidencia, ámbito y tipología del distribuidor.
- **Forescout queda fuera del portfolio Westcon Iberia**: `westcon_fit` se sanea contra el dataset activo de fabricantes y elimina cualquier nombre no perteneciente al portfolio.
- **Clientes privados completos**: 35 componentes IBEX 35 + 16 componentes PSI como cobertura estructural mínima.
- **Contratación pública**: snapshot de expedientes tecnológicos ES/PT con enlaces directos al anuncio concreto; collector adicional TED + PLACSP para ampliar dinámicamente la cobertura sin publicar portadas genéricas.
- **Grafo fabricante ↔ integrador** bidireccional y basado en evidencia. Se amplían localizadores, programas de partners, premios, certificaciones, casos y directorios oficiales, además de la investigación recíproca desde integradores.

## Motor de investigación

- Presupuestos de crawling ampliados para partner pages, sitemaps, ecosistemas, empleo y procurement.
- Mayor universo conocido de integradores/mayoristas para correlación y descubrimiento.
- Prioridad de investigación para fabricantes con menos de tres integradores observados.
- Fuentes añadidas: Channel Partner, IT Channel Portugal, BME, Euronext, PLACSP, TED, BASE, Nokia, AudioCodes, FireMon, Menlo, XM Cyber, Check Point, Zscaler, Vectra AI, Extreme Networks, RUCKUS, 1Password, Penguin/Stratus y otros portales oficiales de fabricantes.

## UI / reporting

- Se conservan la capa global de trazabilidad y el scroll estable de tarjetas grandes.
- PDF ejecutivo nativo y PowerPoint ejecutivo continúan activos.
- Ingesta documental y aportaciones manuales continúan fuera de la versión activa.
