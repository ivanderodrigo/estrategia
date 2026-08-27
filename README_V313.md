# Westcon Iberia Decision Intelligence v3.1.3 hotfix

v3.1.3 corrige el problema de calidad detectado tras la primera ejecución útil de v3.1.2: el buscador encontraba información, pero la dimensión usada para buscar se estaba heredando como si fuese la clasificación real del resultado.

## Cambios principales

- **Clasificación semántica independiente de la query.** Una noticia encontrada durante una búsqueda de `customers` ya no se convierte automáticamente en un caso de cliente.
- **Reclasificación útil.** Una noticia de un nuevo CMO/head puede pasar a `hiring`; una compra a `ma`; un premio a `awards`; un caso real a `customers`.
- **Procurement sigue siendo estricto.** La dimensión `procurement` solo se acepta con anclas de contratación suficientes; `Awards` nunca basta.
- **Filtro geográfico.** Para entidades Iberia/ES/PT se exige un ancla local razonable. Un resultado de Brasil para `Axians Portugal` o `Claranet Portugal` se rechaza salvo que el artículo se refiera explícitamente a la entidad local.
- **Queries con ancla geográfica.** Las búsquedas de entidades ES/PT añaden España/Portugal cuando la marca no lo contiene.
- **Frescura.** Daily rechaza señales demasiado antiguas; weekly y monthly permiten ventanas más amplias.
- **Saneamiento retroactivo.** Las señales guardadas por v3.1.2 se vuelven a validar al arrancar. Las débiles se eliminan y las mal etiquetadas se reclasifican.
- **Diagnóstico ampliado.** Se muestran rechazos por entidad, geografía, antigüedad y semántica, además de cuántas señales se reclasificaron.
- **GDELT.** Se añade un reintento corto y se registra el detalle del último error HTTP/red sin bloquear la actualización.
- **Integradores.** Se incorporan `ma` y `competitive` a sus gaps, porque ambos son relevantes para inteligencia de canal.

## Instalación

Copiar el contenido del hotfix encima del repositorio y reemplazar archivos coincidentes. No borrar `.git`, `.venv` ni `data`.

```powershell
python tools/aplicar_v313.py
Get-Content VERSION
python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy
```

La primera ejecución v3.1.3 puede mostrar `prior quality removed > 0`: es intencionado. Significa que está retirando del dataset señales v3.1.2 que no superan los nuevos criterios.
