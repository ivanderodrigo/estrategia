# Westcon Iberia Business Intelligence v3.6.1

Actualización de profundidad de inteligencia y calidad de exportación, sin cambiar la estructura visible de la aplicación.

## Qué cambia

- Se mantiene exactamente la navegación de cinco áreas: Fabricantes, Integradores, Mayoristas, Tendencias y Arquitecturas.
- La capa pública incluida contiene 36 fabricantes Westcon, 91 partners/integradores, 11 mayoristas competidores, 15 tendencias y 12 arquitecturas.
- El catálogo de investigación incluido alcanza 216 fuentes/familias.
- El enriquecimiento cruza fabricante → partner y partner → fabricante, además de directorios, awards, niveles de programa, casos públicos, certificaciones, servicios, capacidades, empleo/ATS y otras evidencias.
- La relación fabricante-partner requiere evidencia explícita; una vacante solo puede enriquecer skills/perfiles/tecnologías.
- Los informes PDF y PowerPoint adoptan el mismo sistema visual que la web: navy Westcon, acentos cyan/orange/pink/blue/green, tarjetas, cabeceras, contadores y apéndices de fuentes.
- El PDF deja de ser una tabla plana: Fabricantes/Integradores/Mayoristas se paginan en tablas visuales legibles; Tendencias y Arquitecturas se presentan como fichas equivalentes a las de la aplicación.
- El PowerPoint deja de ser una lista de texto: incorpora portada, separadores de sección, tarjetas por entidad, fichas de Tendencias/Arquitecturas y slides de fuentes con enlaces.
- Las exportaciones siguen siendo descriptivas: no incorporan recomendaciones ni campos internos.

## Validación

```powershell
python -m unittest tests/test_v360.py
python scripts/v36/validate_v36.py
node --check assets/v360/intelligence.js
node tests/ui_smoke_v360.js
```

## Despliegue

Conserva `.git`, sustituye el resto por el contenido del paquete y ejecuta:

```powershell
git status
git add -A
git commit -m "Upgrade Business Intelligence v3.6.1"
git pull --rebase origin main
git push origin main
```
