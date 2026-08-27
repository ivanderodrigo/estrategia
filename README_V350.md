# Westcon Iberia Business Intelligence v3.5.0

## Objetivo de esta versión

v3.5.0 convierte la aplicación en una herramienta estrictamente descriptiva de inteligencia estratégica para Iberia. La interfaz pública queda limitada a cinco ámbitos:

1. Fabricantes
2. Integradores
3. Mayoristas de la competencia
4. Tendencias
5. Arquitecturas

La aplicación no genera ni publica acciones, decisiones aconsejadas, prioridades comerciales o prescripciones. La complejidad se mantiene en la investigación, correlación, deduplicación, clasificación y trazabilidad de fuentes.

## Cambios principales

- Navegación principal reducida a cinco áreas de inteligencia.
- Trazabilidad campo a campo: cada dato publicado conserva su evidencia y la interfaz la muestra al hacer hover/foco.
- Cabeceras que pueden inducir dudas incluyen `?` con explicación contextual.
- Las columnas sin datos desaparecen automáticamente para el conjunto filtrado que se está visualizando.
- Se han retirado de la salida final campos internos como tiers, prioridades de profundidad, prioridades de activación, gaps internos o puntuaciones no intuitivas.
- Westcon queda excluido de la tabla de mayoristas competidores.
- Las ofertas de empleo se usan como señal de skills, tecnologías y perfiles demandados, nunca como prueba de partnership, ventas o cuota.
- Las arquitecturas publican contexto, capas, fabricantes, integraciones respaldadas y cautelas; no publican oportunidad, monetización, servicios aconsejados ni readiness.
- El catálogo operativo alcanza 192 fuentes/familias públicas, incluyendo fabricantes, partner locators, distribuidores, integradores, analistas, organismos, contratación pública, medios especializados, portales de empleo, comunidades, estándares y datasets técnicos.
- Las señales de analistas financieros de compra/venta/precio objetivo se descartan como ruido para este producto.
- Los ciclos diario, semanal y mensual publican con el supervisor `research_supervisor_v35.py` y validan las reglas de esta versión antes del commit automático.

## Arquitectura de publicación

La investigación existente v3.1-v3.3 continúa actuando como foundation. v3.5 reconstruye entidades, relaciones, señales de ecosistema, cobertura de fuentes y arquitecturas, y después genera `data/v35/intelligence.json`, que es la única capa consumida por el frontend.

El pipeline v3.5 no importa ni ejecuta el motor anterior de acciones. Los artefactos de ese motor se eliminan de `data/v34/` al publicar v3.5.

## Instalación sobre el repositorio existente

La opción más segura es conservar exclusivamente `.git` de la instalación anterior, borrar el resto del contenido del directorio de trabajo y copiar dentro todo el contenido de este paquete. Después:

```powershell
git status
git add -A
git commit -m "Upgrade Business Intelligence v3.5.0"
git pull --rebase origin main
git push origin main
```

Si `git pull --rebase` detecta cambios remotos incompatibles, resolverlos antes de continuar el rebase; no usar `--force` como procedimiento normal.

## Validación local rápida

```powershell
python -m unittest tests/test_v350.py
python scripts/v35/validate_v35.py
node --check assets/v350/intelligence.js
node tests/ui_smoke_v350.js
```

Para reconstruir solamente la capa v3.5 usando la última investigación disponible:

```powershell
python scripts/research_supervisor_v35.py --profile daily --skip-v33
```

## Salida actual incluida

- 86 fabricantes
- 47 integradores
- 11 mayoristas competidores
- 15 tendencias
- 12 arquitecturas
- 192 fuentes/familias de investigación
- 777 campos publicados con evidencia asociada

Estas cifras no son objetivos rígidos: evolucionan con la evidencia disponible. Un campo sin evidencia no se publica.
