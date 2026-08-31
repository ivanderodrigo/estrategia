# Informe de limpieza

La limpieza no se hace por antigüedad o por nombre: se hace por **referenciabilidad del runtime**.

El UPDATE_ONLY consulta `git ls-files`, preserva `.git` y cualquier archivo no versionado del usuario, respalda transaccionalmente los archivos versionados que vaya a sustituir/eliminar y solo consolida la operación si pasan VERSION, Python tests, validación canónica y smoke JS cuando Node está disponible. Si falla, restaura los archivos respaldados.

El histórico útil sigue disponible en Git. No se mantiene dentro del runtime una copia de cinco o más generaciones solamente por seguridad aparente.
