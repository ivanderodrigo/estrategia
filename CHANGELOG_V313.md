# v3.13.0 · Evidence Coverage Engine

## UX
- Las tarjetas de trazabilidad y ayuda **ya no se abren por hover**. Se abren deliberadamente por clic (o Enter/Espacio), permanecen abiertas mientras se leen/scrollan y se cierran con clic exterior, `Esc` o `×`.
- Las columnas con cobertura inferior al 20% se ocultan temporalmente en tablas grandes para reducir ruido visual; siguen formando parte de la cola de investigación y reaparecen al alcanzar cobertura.

## Investigación hiperprofunda
- Nuevo **gap engine dinámico v3.13**: calcula los huecos sobre el dataset actual, en vez de heredar el antiguo contador de 559 gaps.
- Cada hueco genera hasta 10 rutas dirigidas: fuente oficial de entidad, fuente oficial recíproca de fabricante, casos, certificaciones, servicios, empleo, canal y evidencia de mercado/contratación según el campo.
- Las páginas oficiales de integradores/mayoristas ya se aprovechan para servicios, capacidades, especializaciones, verticales, casos y empleo **aunque no mencionen un fabricante Westcon**. Antes se descartaban, causando gran parte de las celdas vacías.
- Las señales de empleo pueden poblar perfiles/tecnologías, pero **nunca prueban por sí solas una relación de partnership**.
- Universo de dominios oficiales ampliado: 144 integradores, 66 distribuidores y 51 grandes cuentas IBEX 35/PSI como semillas de descubrimiento.
- Investigación de las 51 grandes cuentas desde sus dominios corporativos: tecnología, cloud, seguridad, networking, casos y empleo.

## Presupuestos de investigación
- Daily: hasta 320 queries y 900 páginas de ecosistema.
- Deep: hasta 900 queries y 3.200 páginas de ecosistema, con las 51 grandes cuentas incluidas.
- Exhaustive: hasta 1.600 queries y 6.000 páginas de ecosistema.
- Se mantienen retries, circuit breaker, checkpoint/resume y publicación parcial segura.

## Nuevas rutas/fuentes
- AWS Partner Discovery.
- Cisco Partner Finder / Evolved Partner Ecosystem.
- Channel Partner Ranking del Canal TIC 2026.
- IT Channel Portugal: directorio general y de distribuidores.
- PLACSP Datos Abiertos y TED Search API.
- dados.gov.pt / IMPIC: contratos y anuncios de Portal BASE 2012–2026.

## Cobertura inicial del snapshot
- 36 fabricantes, 60 mayoristas validados, 130 integradores, 81 clientes, 15 tendencias y 12 arquitecturas.
- 278 fuentes/familias en catálogo.
- 1.881 campos trazables en el snapshot de construcción.
- El contador de gaps pasa a ser real y explícito; el objetivo de la automatización es reducirlo progresivamente sin inventar datos.
