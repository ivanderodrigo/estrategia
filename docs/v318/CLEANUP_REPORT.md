# Informe de limpieza v3.18.0

- Eliminados únicamente `__pycache__` y ficheros `.pyc`, al ser artefactos regenerables y seguros.
- No se borraron versiones históricas, datasets grandes ni scripts heredados sin demostrar ausencia de dependencia.
- Se clasificó el histórico como KEEP/MIGRATE/REVIEW en la auditoría.
- No se encontraron ZIPs de release dentro del runtime nuevo ni backups `.bak` necesarios para borrar automáticamente.
