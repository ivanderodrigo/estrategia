# Westcon Iberia Decision Intelligence v3.4.0 — Production Candidate

Esta versión transforma la baseline completa v3.3.3a en una plataforma de **Business + Technology Decision Intelligence**. El repositorio funciona como aplicación estática y pipeline Python; no requiere una base de datos ni contenido de pago.

## 1. Resumen ejecutivo

v3.4 sustituye el gate absoluto de recomendaciones por un contrato de decisión que separa:

- confianza en los hechos;
- confianza en la interpretación;
- riesgo de la acción.

Una señal material pasa a **ACTUAR**, **PREPARAR / VALIDAR**, **INVESTIGAR** o **VIGILAR**. Solo se descarta cuando no merece atención ejecutiva, está duplicada o no tiene evidencia; la disposición queda auditada.

La versión añade además:

- Executive Decision Brief orientado a Dirección;
- tablas de integradores y mayoristas con filosofía común, filtros, orden, selección, movimiento, persistencia y CSV;
- ocultación de variables internas y columnas con menos del 20 % de cobertura;
- inteligencia Integrador/Mayorista × Fabricante con estado, intensidad, confianza y geografía separados;
- partner locators, niveles, certificaciones, especializaciones y casos oficiales como evidencias de relación diferenciadas;
- cruce de fabricantes movidos, perfiles buscados y señales de empleo, sin confundir vacantes con partnership o headcount;
- catálogo operativo de 129 fuentes públicas/gratuitas;
- aprendizaje de fuentes por entidad × dimensión × país × tipo;
- 12 arquitecturas originales orientadas a monetización, recurrencia, servicios y readiness;
- histórico móvil de 30/90/365 días;
- informe PDF ejecutivo y presentación PowerPoint narrativa, no capturas del dashboard;
- instalación/migración segura e idempotente desde v3.3.3a.

## 2. Problemas encontrados en v3.3.3a

1. El frontend exigía confianza exactamente 100/100 y al menos tres evidencias para mostrar una acción. La baseline real publicaba **0 acciones**, aunque existían señales materiales.
2. 80 repeticiones de evidencia aparecían en matrices de relación y podían inflar recuentos e intensidad.
3. Cuatro fabricantes estaban clasificados también como integradores: Cisco, Fortinet, Infoblox y Arista Networks.
4. El modelo mezclaba ausencia de prueba pública con una lectura próxima a “no existe relación”.
5. Estado, intensidad y confianza de la relación no estaban gobernados de forma suficientemente explícita.
6. Había solo cinco arquitecturas de la capa anterior y algunas incluían entidades con rol incorrecto.
7. La vista de integradores/mayoristas tenía menos profundidad y control de columnas que fabricantes.
8. Columnas internas —por ejemplo, “Prioridad de profundidad”— podían aparecer a usuarios; otras casi vacías consumían espacio.
9. Los workflows semanal y mensual usaban perfiles `deep` y `exhaustive` que el supervisor v3.3 no aceptaba directamente.
10. El smoke test de UI tenía un KPI numérico fijo y fallaba al cambiar el dataset.
11. Dos de 106 tests unitarios fallaban: una expectativa de versión obsoleta y una validación de provenance que omitía filas legacy.
12. Existía dependencia importante de enlaces de agregador en parte de la evidencia; la fuente primaria sigue siendo una deuda prioritaria.
13. Una métrica de éxito de fuente podía superar 1,0 al dividir evidencias aceptadas por consultas; v3.4 la limita a 0–1.
14. La clasificación heredada de contratación podía aceptar falsos positivos. v3.4 exige lenguaje explícito de vacante o inversión de plantilla.

## 3. Mejoras realizadas

### Recomendaciones

Cada recomendación incluye acción, por qué, por qué ahora, evidencias, confianza factual e interpretativa, riesgo, tipo, impacto, urgencia, esfuerzo, horizonte, responsable, entidades implicadas, servicios, recurrencia, margen relativo, riesgos, información pendiente, condición de cambio, fuentes y fechas.

El archivo `data/v34/recommendation_audit.json` comprueba invención, evidencia ausente, ausencia injustificada, exceso, genericidad, duplicados, contradicciones, falta de verbo de acción y acciones demasiado fuertes.

### Ecosistema y fuentes

`data/v34/ecosystem_motion_intelligence.json` cruza para 40 entidades prioritarias:

- fabricantes confirmados;
- fabricantes probables;
- relaciones a investigar;
- fabricantes/certificaciones mencionados en perfiles buscados;
- familias de perfiles y momentum 30/90/365;
- fuentes y queries siguientes.

El orden de evidencia de relación es: partner locator oficial, nivel de partnership, certificación/especialización, caso de éxito del fabricante, premio, marketplace, caso del integrador y perfil de empleo. Cada tipo declara qué demuestra y qué **no** demuestra.

`data/v34/source_catalog.json` contiene 129 fuentes con URL, acceso, ámbito, clase, dimensiones, método, periodicidad, prioridad y algoritmos que alimenta. Incluye fuentes donde el ecosistema realmente trabaja e investiga: portales de fabricante y partner, casos, certificaciones, academias, eventos, comunidades, marketplaces, advisories/PSIRT, contratación pública, subvenciones, regulación, empleo, registros, economía, telecom, financiación, M&A, installed-base pasiva y medios de canal.

Las fuentes premium solo pueden aportar metadatos o resúmenes públicos. No se reconstruyen informes de pago.

### UX, informes y arquitectura

- Variables del planificador interno no se ofrecen como columnas.
- Una columna se auto-oculta si menos del 20 % de las filas tiene información.
- Las preferencias visibles se guardan en `localStorage` del navegador.
- La tabla permite búsqueda, filtro país, orden, selección, reordenación y CSV.
- La portada responde en menos de un minuto a qué cambió, por qué importa y qué hacer.
- PDF/PPT incluyen situación, tendencias, portfolio, ecosistema, oportunidades, amenazas, recomendaciones, plays, arquitecturas, roadmap, KPIs, riesgos, método y fuentes.

## 4. Resultados de pruebas

| Prueba | Resultado |
| --- | --- |
| Baseline v3.3.3a unit tests | 106 ejecutados; 104 PASS; 2 FAIL |
| Baseline UI smoke | FAIL por gate/KPI rígido |
| v3.4 unit/regression suite | **127/127 PASS** |
| Sintaxis JavaScript | **PASS** en todos los assets |
| UI smoke legacy actualizado | **PASS** |
| UI smoke v3.4 | **PASS** |
| `tools/validar_v340.py` | **PASS** |
| `tools/auditar_v340.py` | **PASS**, 1 warning honesto |
| Migración real desde copia v3.3.3a | **PASS** |
| Ejecución daily offline | **PASS / published** |
| Ejecución weekly offline | **PASS / published** |
| Workflows daily/weekly/monthly | **PASS** por validación estática y tests |

La revisión en navegador cloud no pudo abrir `localhost` por una restricción del entorno de revisión. La aplicación sí pasó carga HTTP local, contratos DOM/JSON, smoke runtime y sintaxis; la validación visual final debe repetirse con el procedimiento de la sección 10 en el equipo de revisión.

## 5. Auditoría de calidad

- Estado: **PASS**.
- Checks: 23.
- PASS: 22.
- Warnings: 1.
- Errores: 0.
- Auditoría de recomendaciones: **PASS**, 0 errores, 0 warnings.
- Recomendaciones inventadas: 0.
- Recomendaciones sin evidencia: 0.
- Recomendaciones genéricas: 0.
- Duplicadas: 0.
- Contradictorias: 0.
- Acciones demasiado fuertes: 0.
- Relaciones con evidencia duplicada en v3.4: 0.
- Conflictos de identidad sin resolver: 0.

El warning conserva siete evidencias de más de tres años. Siguen trazadas, pero no elevan por sí solas una relación a confirmada.

## 6. Métricas antes/después

| Métrica | v3.3.3a | v3.4.0 |
| --- | ---: | ---: |
| Perfiles de ecosistema | 83 | 79 |
| Integradores visibles | 69 | 65 |
| Mayoristas | 14 | 14 |
| Filas de relación | 3.237 | 3.081 |
| Evidencias de relación duplicadas | 80 | 0 |
| Acciones publicadas con el gate antiguo | 0 | n/a |
| Recomendaciones graduadas | n/a | 24 |
| PREPARAR / VALIDAR | n/a | 18 |
| INVESTIGAR | n/a | 3 |
| VIGILAR | n/a | 3 |
| ACTUAR | n/a | 0 |
| Arquitecturas | 5 en la capa anterior | 12 |
| Catálogo operativo v3.4 | n/a | 129 fuentes |
| Candidatos totales de fuente | 151 registry | 280 registry + expansión |
| Perfiles de movimiento/talento | n/a | 40 |
| Señales de talento aceptadas | n/a | 5 |
| Falsos positivos de hiring rechazados | n/a | 1 |
| Tests | 104/106 PASS | 127/127 PASS |

No se publica ninguna acción **ACTUAR** porque el dataset incluido no cumple conjuntamente la exigencia factual, interpretativa, de riesgo y fuente primaria. Es un resultado correcto: v3.4 muestra acciones útiles de validación, investigación o vigilancia sin fabricar certeza.

La cobertura media baja de 26,7 % a 12,6 % porque v3.4 mide un conjunto mucho más amplio de campos de negocio. No representa pérdida de evidencia; refleja deuda de conocimiento antes invisible.

## 7. Problemas conocidos

1. Siete evidencias antiguas permanecen como contexto histórico.
2. 78 de 79 perfiles no alcanzan todavía 50 % del nuevo esquema ampliado.
3. Algunas evidencias heredadas son URLs de Google News; deben resolverse a la fuente original.
4. BASE Portugal y varios directorios pueden cambiar HTML, aplicar límites o requerir sesión; un fallo no rompe el pipeline.
5. Los locators no siempre muestran fecha; v3.4 conserva “Fecha no publicada” y la fecha de consulta debe registrarse en futuros runs.
6. PDF y PPT dependen de librerías CDN en el navegador. Si se trabaja sin Internet, la aplicación funciona, pero esas exportaciones no estarán disponibles.
7. No se ha introducido información interna de ventas, margen, pipeline, rebates, renewals o capacidad; economics siguen siendo relativos.

## 8. Deuda restante

- Completar campos de integradores/mayoristas con prioridad en entidades de mayor relevancia.
- Resolver redirects de agregador a URLs editoriales/primarias.
- Añadir snapshots comparables de contratación para calcular hiring momentum real por vendor y trimestre.
- Completar partner level, certificaciones y casos por España y Portugal desde los locators oficiales.
- Incorporar de forma opcional ventas, margen, pipeline, rebates, renewals, attach, base de partners, headcount y coste de enablement bajo un esquema separado y gobernado.
- Automatizar render visual del PDF/PPT en CI cuando exista un navegador disponible.

## 9. Instalación EXACTA sobre una copia actual de v3.3.3a

La instalación recomendada es **side-by-side**. No descomprima encima de su carpeta actual.

### Windows PowerShell

Suponga que su carpeta actual se llama `estrategia` y el ZIP está en la misma carpeta padre:

```powershell
cd C:\ruta\al\directorio-padre
Rename-Item .\estrategia .\estrategia-v333a-backup
Expand-Archive .\Westcon_Iberia_Decision_Intelligence_v3.4.0_Production_Candidate.zip -DestinationPath .
Rename-Item .\Westcon_Iberia_Decision_Intelligence_v3.4.0_Production_Candidate .\estrategia
cd .\estrategia
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python tools\aplicar_v340.py --migrate-from ..\estrategia-v333a-backup
python tools\validar_v340.py
```

Si `Activate.ps1` está bloqueado, use directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\aplicar_v340.py --migrate-from ..\estrategia-v333a-backup
.\.venv\Scripts\python.exe tools\validar_v340.py
```

### Linux/macOS

```bash
cd /ruta/al/directorio-padre
mv estrategia estrategia-v333a-backup
unzip Westcon_Iberia_Decision_Intelligence_v3.4.0_Production_Candidate.zip
mv Westcon_Iberia_Decision_Intelligence_v3.4.0_Production_Candidate estrategia
cd estrategia
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python tools/aplicar_v340.py --migrate-from ../estrategia-v333a-backup
python tools/validar_v340.py
```

`tools/aplicar_v340.py` acepta solo una carpeta separada con `VERSION` exactamente `3.3.3a`, crea un backup local de los datos destino, copia datos dinámicos y reconstruye v3.4. Es idempotente.

## 10. Validación EXACTA de la instalación

Con el entorno virtual activo, desde la raíz de `estrategia`:

```powershell
python tools\validar_v340.py
python tools\auditar_v340.py
python -m unittest discover -s tests -p "test*.py" -v
node scripts\ui_smoke.js
node tests\ui_smoke_v340.js
```

Resultado esperado:

- `VALIDACIÓN v3.4.0 · PASS`;
- auditoría con `Calidad: PASS` y, como máximo, warnings documentados;
- `Ran 127 tests ... OK`;
- dos mensajes `OK` de UI.

Compruebe además:

```powershell
Get-Content .\VERSION
python -m json.tool data\v34\quality_report.json > $null
python -m json.tool data\v34\recommendation_audit.json > $null
```

`VERSION` debe mostrar `3.4.0`.

## 11. Prueba daily EXACTA

### Offline/determinista con los datasets incluidos

```powershell
python scripts\research_supervisor_v34.py --profile daily --max-runtime 180 --skip-v33
python tools\validar_v340.py
```

### Daily completo con investigación pública

```powershell
python scripts\research_supervisor_v34.py --profile daily --max-runtime 720
python tools\validar_v340.py
```

Debe terminar con `v3.4.0 published`, `quality PASS` y `recommendation audit PASS`. Un fallo de una fuente puede producir warning/fallback; no debe borrar el último dataset válido.

## 12. Prueba weekly EXACTA

### Offline/determinista

```powershell
python scripts\research_supervisor_v34.py --profile weekly --max-runtime 240 --skip-v33
python tools\validar_v340.py
```

### Weekly completo

```powershell
python scripts\research_supervisor_v34.py --profile deep --max-runtime 1800 --fallback-runtime 240
python tools\validar_v340.py
```

`deep` es un alias compatible de `weekly`. El workflow semanal utiliza ese alias.

## 13. Prueba local EXACTA de la aplicación

```powershell
python -m http.server 8000
```

Abra [http://localhost:8000](http://localhost:8000) y compruebe:

1. La portada muestra `Executive Decision Brief` y acciones por tipo.
2. Las recomendaciones tienen Acción, Por qué, Por qué ahora y las tres variables de confianza/riesgo.
3. Abra una recomendación y pulse sus fuentes.
4. En Integradores, busque `Logicalis`, ordene por Potencial de activación y seleccione la fila.
5. Confirme “Fabricantes que mueve”, “Perfiles que busca”, estado/intensidad/confianza y gaps.
6. Confirme que “Prioridad de profundidad” no aparece en el selector de columnas.
7. Confirme que la barra indica columnas con cobertura insuficiente ocultas.
8. En Mayoristas, filtre España/Portugal, reordene una columna y exporte CSV.
9. Recargue: el orden/selección de columnas debe persistir.
10. En Arquitecturas, compruebe las 12 arquitecturas y que las integraciones aparecen `A VALIDAR`.
11. En Tendencias, compruebe 30/90/365.
12. En Fuentes, compruebe source learning y la mención de fuentes de contratación.
13. Genere PDF/PPT con Internet disponible y revise portada, narrativa, legibilidad y páginas/slides.
14. Repita con ventana de 390 × 844 px; no debe haber solapes de texto ni navegación inaccesible.

Detenga el servidor con `Ctrl+C`.

## 14. Qué ficheros se copian o reemplazan

No copie 30 ficheros manualmente. Instale el ZIP completo en una carpeta nueva.

El código, frontend, tests, workflows y configuración de v3.4 sustituyen a los de la carpeta activa completa. El migrador copia desde v3.3.3a únicamente:

- `data/history/`;
- `data/v31/`, `data/v32/`, `data/v33/`;
- `diagnostics/`;
- `.v32_state/`;
- `data/research.latest.json`;
- `data/research_status.json`;
- `data/research_learning.json`;
- `data/research_queue.json`;
- `data/changes.latest.json`;
- `data/source_health.json`;
- `data/discovered_entities.json`;
- `data/research_errors.json`;
- `data/run_manifest.latest.json`;
- `data/supervisor.latest.json`;
- `config/update_schedule.json`.

Después regenera `data/v34/`.

## 15. Datos que deben preservarse

Preserve siempre la carpeta completa `estrategia-v333a-backup` hasta aprobar v3.4. Dentro de ella son especialmente importantes:

- histórico y snapshots válidos;
- aprendizaje, colas y salud de fuentes;
- configuración horaria;
- diagnósticos útiles;
- cualquier dataset privado o personalizado que usted haya añadido;
- archivos de entrada internos no incluidos en el repositorio.

Los datos internos no deben mezclarse con outputs públicos sin revisar su esquema y permisos.

## 16. Qué NO debe borrar

No borre:

- la copia completa `estrategia-v333a-backup`;
- `data/history/`;
- `.v32_state/` de su instalación actual antes de migrar;
- `data/research_learning.json`, `data/research_queue.json` o `data/source_health.json`;
- `config/update_schedule.json` personalizado;
- datos privados/custom no presentes en el ZIP;
- `.local-backups/` creado por el migrador hasta completar la aceptación.

El ZIP entregado no contiene `.git`, `.venv`, `node_modules`, caches, backups ni temporales.

## 17. Vuelta atrás

La vuelta atrás más segura restaura la carpeta completa:

```powershell
cd C:\ruta\al\directorio-padre
Rename-Item .\estrategia .\estrategia-v340-failed
Rename-Item .\estrategia-v333a-backup .\estrategia
```

Si solo quiere revertir la copia de datos dentro de v3.4:

```powershell
cd .\estrategia-v340-failed
python tools\aplicar_v340.py --rollback-migration
```

Ese comando restaura datos; la aplicación sigue siendo v3.4. Para volver realmente a v3.3.3a use la carpeta completa preservada.

## 18. Commit y push posteriores — no ejecutados

Revise primero el contenido y el estado:

```bash
git status --short
git diff --stat
python tools/validar_v340.py
python -m unittest discover -s tests -p "test*.py" -v
node scripts/ui_smoke.js
node tests/ui_smoke_v340.js
```

Cuando usted lo apruebe:

```bash
git switch -c release/v3.4.0-production-candidate
git add -A
git commit -m "release: Westcon Iberia Decision Intelligence v3.4.0"
git push -u origin release/v3.4.0-production-candidate
```

Abra después una pull request, revise Actions/Pages y haga el merge según su proceso. Esta entrega **no** ha hecho push, merge ni cambios en repositorios externos.

## Outputs clave

| Fichero | Uso |
| --- | --- |
| `data/v34/recommendations.json` | Recomendaciones ejecutivas |
| `data/v34/recommendation_audit.json` | Auditoría específica de recomendaciones |
| `data/v34/quality_report.json` | Quality gates y deuda honesta |
| `data/v34/source_coverage.json` | Aprendizaje y cobertura de fuentes |
| `data/v34/source_catalog.json` | Catálogo operativo de 129 fuentes |
| `data/v34/business_intelligence_report.json` | Executive Decision Brief |
| `data/v34/ecosystem_motion_intelligence.json` | Fabricantes movidos y perfiles buscados |
| `data/v34/relationships.json` | Integrador/Mayorista × Fabricante |
| `data/v34/architectures.json` | Arquitecturas originales |
| `data/v34/historical_intelligence.json` | Ventanas 30/90/365 |
| `data/v34/research_queue.json` | Investigación adaptativa |
| `data/v34/metrics_before_after.json` | Métricas comparables y explicación |

