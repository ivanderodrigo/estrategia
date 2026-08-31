# Changelog v3.17.0

- Corregido el fallo de Actions causado por `scripts/publish_research_update.py`, que seguía ejecutando el validador eliminado de v3.12.
- Eliminado el fallback roto de configuración profunda mediante una configuración de compatibilidad versionada.
- Publicador automático con detección de `VERSION`, snapshot de salidas vigentes, validación y reintentos sobre `origin/main`.
- Workflows diarios, semanales y mensuales migrados íntegramente a v3.17.
- Añadidas las dos columnas de ecosistema fabricante en mayoristas e integradores.
- Clasificación automática de relaciones ya trazadas contra el portfolio Westcon Iberia.
- Cola de investigación ampliada de 32 a 48 estrategias por hueco.
- Limpieza de cachés y exclusión de `.git`, temporales, entornos y versiones de rollback en los paquetes.
