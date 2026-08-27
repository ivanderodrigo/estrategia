# Westcon Iberia Decision Intelligence v3.1.4

Hotfix de calidad semántica sobre v3.1.3.

## Por qué existe

La auditoría manual de las 37 señales saneadas de v3.1.3 mostró que el filtro ya eliminaba mucho ruido, pero todavía confundía eventos distintos:

- entrevistas/posicionamiento con M&A;
- reestructuración de capacidades con certificaciones;
- contratación de productos financieros con hiring;
- responsable de Compras con una compra corporativa;
- premios a distribuidores con acuerdos de distribución;
- programas de premios organizados por una entidad con premios recibidos por esa entidad;
- `SOC` como substring de `socios`;
- señales LATAM de fabricantes globales como si fueran directamente útiles para Iberia;
- noticias históricas descubiertas hoy con movimientos actuales.

## Cambios

### Clasificación

Se endurecen las clases de M&A, hiring, certification y distribution. Se añaden event types para leadership change, capability change, strategy/growth, market signal, partnership y service launch. La query sigue siendo solo un mecanismo de descubrimiento y nunca determina por sí sola la clase final.

### Awards

`Awards` continúa sin poder convertirse en procurement. `Distribuidor del Año` se clasifica como award, no como distribution agreement. Los programas de premios propios (ej. finalistas de `Axians Portugal Digital Awards`) se descartan como señal estratégica de award de la entidad.

### Certificaciones

Una noticia sobre estudiantes que obtienen una certificación con ayuda de un integrador ya no demuestra que el integrador tenga esa certificación/tier.

### Geografía

Para entidades GLOBAL se rechazan eventos explícitamente LATAM-only cuando no existe ancla global, EMEA, europea o ibérica. El dominio del medio no se utiliza como prueba suficiente de geografía del evento.

### Frescura

Se mantiene histórico suficiente para construir contexto, pero cada señal queda marcada como:

- `current` / `is_current_signal=true`
- `historical_context` / `is_current_signal=false`

En daily, `current` significa hasta 90 días. Esto evita confundir una noticia antigua recién descubierta con un movimiento nuevo del mercado.

### Duplicados y corroboración

Las copias sindicadas del mismo titular/evento se colapsan y conservan `corroborating_sources`, `corroborating_urls`, `corroboration_count` y `corroboration_score`.

### GDELT

GDELT queda como best-effort: un solo intento, timeout corto y circuit breaker inmediato. Una caída del endpoint no consume una parte significativa del presupuesto daily y no genera fallo del proceso.

## Instalación

Copiar el contenido del ZIP encima del repositorio v3.1.3, reemplazando archivos coincidentes, y ejecutar desde la raíz:

```powershell
python tools/aplicar_v314.py
Get-Content VERSION
python -m pytest tests/test_v313.py tests/test_v314.py -q
python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy
```

`VERSION` debe mostrar `3.1.4`.
