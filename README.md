# Westcon Iberia Business Intelligence v3.6.1

## Qué es

Aplicación estática de inteligencia de negocio para Westcon Iberia, diseñada para GitHub Pages. La interfaz pública se concentra exclusivamente en cinco ámbitos:

1. Fabricantes
2. Integradores
3. Mayoristas de la competencia
4. Tendencias
5. Arquitecturas

La interfaz es deliberadamente sencilla; la investigación, deduplicación, extracción de relaciones, aprendizaje de fuentes, clasificación geográfica y trazabilidad se mantienen en el backend.

## Cambios v3.6

- Control de tamaño de texto `A− / 100% / A+`, persistente en el navegador y con escala del 90% al 150%.
- Fabricantes: las filas corresponden exactamente a los 36 fabricantes del portfolio Westcon Iberia incluido en la base. La competencia aparece como contexto de cada fabricante, no como filas independientes.
- Competencia por fabricante: se conservan todos los peers/competidores encontrados con evidencia, sin truncarlos visualmente.
- Integradores: el motor amplía la investigación a integradores, instaladores, reseller/VAR, MSP, MSSP, service providers, consultoras y partners certificados de los fabricantes Westcon.
- Descubrimiento de ecosistema: partner locators, directorios oficiales, niveles de partner, premios, casos, customer stories, páginas de alianzas, marketplaces, certificaciones, contratación pública, portales de empleo y ATS.
- Las vacantes solo enriquecen skills, tecnologías, certificaciones y perfiles; nunca crean por sí solas una relación fabricante-partner.
- Tendencias: 15 fichas enriquecidas con mercado/crecimiento, horizonte, drivers, demanda observada, panorama de fabricantes, fabricantes Westcon relacionados, evolución y contexto Iberia cuando existe evidencia.
- Arquitecturas: 12 marcos funcionales definidos primero a partir de analistas/estándares y mapeados después contra capacidades explícitas del portfolio Westcon.
- UiPath se clasifica en automatización/orquestación agéntica. Puede aparecer como capacidad adyacente de workflow o governance cuando existe soporte documental, pero no como plataforma Identity.
- Catálogo: 210 fuentes/familias de investigación, con nuevas rutas específicas para directorios de partners, MSP/MSSP, employment/ATS y marcos de arquitectura.
- Trazabilidad por dato y por entidad; las columnas sin información desaparecen automáticamente.

## Arquitectura de investigación

El supervisor v3.6 utiliza la investigación pública existente como foundation y añade una estrategia específica de expansión de ecosistema:

- búsquedas por fabricante y país;
- consultas en dominios oficiales de fabricante;
- `partner locator`, `find a partner`, `partner directory`;
- reseller, VAR, instalador/integrador, MSP, MSSP, solution/service provider;
- partners certificados, niveles y premios;
- casos y customer stories;
- páginas propias de alianzas de los partners;
- portales de empleo y ATS para descubrir skills y tecnologías;
- aprendizaje de entidades descubiertas para ciclos posteriores.

La publicación exige evidencia explícita para vincular un partner con un fabricante Westcon. Los candidatos de investigación sin prueba suficiente permanecen fuera de la interfaz.

## Arquitecturas v3.6

Se elimina del pipeline activo el antiguo generador de arquitecturas por afinidad de dominio/materialidad. La capa pública se construye desde marcos funcionales explícitos apoyados en Gartner, Forrester, IDC, NIST y documentación técnica relevante, y solo entonces se mapean capacidades del portfolio Westcon.

Marcos incluidos:

- SASE / SSE
- Zero Trust
- Identity Security
- AI Security
- Modern SOC / SecOps
- Network Platform / AIOps
- Secure Campus / LAN
- OT / CPS Security
- AI-ready Data Center & Edge
- Observability / Digital Experience
- NaaS / Managed Networking
- Agentic Automation

## Validación local

```powershell
python -m unittest tests/test_v360.py
python scripts/v36/validate_v36.py
node --check assets/v360/intelligence.js
node tests/ui_smoke_v360.js
```

Para reconstruir la capa pública reutilizando la última investigación disponible:

```powershell
python scripts/research_supervisor_v36.py --profile daily --skip-v33
```

## Despliegue sobre el repositorio existente

Conserva `.git`, sustituye el resto del contenido por este paquete y ejecuta:

```powershell
git status
git add -A
git commit -m "Upgrade Business Intelligence v3.6.1"
git pull --rebase origin main
git push origin main
```

## Dataset incluido en esta candidata

- 36 fabricantes Westcon
- 91 partners/integradores con relación publicable ya soportada en la snapshot incluida
- 11 mayoristas competidores
- 15 tendencias enriquecidas
- 12 arquitecturas validadas por taxonomía funcional
- 216 fuentes/familias de investigación

El universo de integradores no se considera cerrado: el objetivo del recolector v3.6 es crecer de forma continua a medida que encuentre nuevas relaciones demostrables en los ecosistemas de los fabricantes.

## Mejora v3.6.1

Sin cambiar la estructura visible, v3.6.1 aumenta la cobertura del ecosistema y rediseña las exportaciones para que PDF y PowerPoint mantengan el mismo lenguaje visual de la aplicación: portada Westcon, colores corporativos, tarjetas, cabeceras, contadores y fuentes. Tendencias y Arquitecturas se exportan como fichas, no como tablas planas; el PowerPoint incluye además un apéndice de fuentes con enlaces.
