# Westcon Iberia Decision Intelligence v3.1.5

Hotfix de rendimiento y observabilidad sobre v3.1.4.

## Motivo

La ejecución real de v3.1.4 mostró una latencia media de Google News RSS de ~28,6 s. El motor usaba lotes con barrera: hasta que terminaban las cuatro peticiones del lote no se enviaba trabajo nuevo. Resultado: solo 18 consultas útiles en 167 s.

## Cambios

- Ejecutor con **continuous refill**: cada worker que termina recibe trabajo inmediatamente.
- `daily`: 8 workers, sin búsquedas `site:` adicionales; estas pasan a weekly/monthly y, sobre todo, a conectores directos en v3.2.
- Google News continúa como discovery general, con pista temporal `after:YYYY-MM-DD` (120 días en daily). La fecha se vuelve a validar después; el operador solo ayuda al descubrimiento.
- GDELT pasa a **un health probe por ejecución** mientras su endpoint público siga agotando timeout. No ocupa un slot por cada gap.
- Prioridad del primer pase orientada a señales de mayor impacto (distribution, M&A, competitive/services según tipo de entidad).
- Nuevo rechazo `secondary_people_move`: evita atribuir a una entidad una noticia de liderazgo cuyo protagonista real pertenece a otra compañía y donde la entidad solo aparece como destino contextual.
- Cada nueva señal recibe `first_seen_at`, `last_seen_at`, `last_seen_run_id` y `new_in_run_id`; `meta.run_id` permite auditar exactamente lo descubierto en cada ejecución.
- La salida añade latencia media por proveedor y recuento `secondary-move`.
- No se relajan los filtros semánticos de v3.1.4.

## Instalación

Copiar el contenido del ZIP sobre la raíz del repositorio, reemplazando coincidencias, sin borrar `.git`, `.venv` ni `data`.

```powershell
python tools/aplicar_v315.py
Get-Content VERSION
python tests/test_v315_unittest.py
python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy
```

`VERSION` debe devolver `3.1.5`.

## Pruebas

El hotfix incluye pruebas `unittest` que no requieren `pytest`. Además se verificaron las 25 pruebas funcionales heredadas de v3.1.3/v3.1.4 mediante harness estándar y una simulación de scheduling con latencia: GDELT se intentó una sola vez y el refill continuo mantuvo ocupados los workers.
