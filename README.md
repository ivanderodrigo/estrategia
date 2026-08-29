# Westcon Iberia Business Intelligence v3.12.0

Release centrada en **calidad de clasificación, profundidad de fuentes y cobertura de negocio Iberia**.

## Qué cambia

- **Mayoristas validados positivamente.** Ya no basta con que una empresa aparezca relacionada con fabricantes: debe existir evidencia explícita de que actúa como distribuidor, mayorista o VAD. Fabricantes como Akamai, Cradlepoint, Splunk, Stratus/Penguin, Noname o Forescout no pueden entrar en la tabla por inferencia débil.
- **Portfolio Westcon saneado.** `westcon_fit` solo admite nombres presentes en el portfolio activo del dataset; Forescout queda fuera.
- **Grandes cuentas completas.** La cobertura mínima de clientes privados pasa a ser IBEX 35 completo en España y PSI completo en Portugal.
- **Más contratación pública y mejor trazabilidad.** Cada fila publicada debe apuntar al anuncio/expediente oficial concreto. La v3.12 incorpora un snapshot amplio y un collector dinámico TED + PLACSP.
- **Más integradores y más relaciones por fabricante.** El grafo se alimenta en ambas direcciones: fabricante → partner locator/directorios/casos/premios/certificaciones y integrador → portfolio/alianzas/casos/certificaciones. La relación solo se publica con evidencia.
- **Investigación más profunda.** Se elevan los límites de anchors, páginas de partner, sitemaps, búsqueda de ecosistema, portales de empleo y contratación pública.

## Principios de clasificación

1. `Mayoristas`: positive-validation-first.
2. `Fabricantes`: portfolio Westcon activo + contexto competitivo; no se convierten en mayoristas por vender directa o indirectamente.
3. `Integradores`: entidad validada + relaciones fabricante↔integrador evidenciadas y bidireccionales.
4. `Clientes públicos`: expediente concreto, nunca una portada genérica del portal.
5. `Clientes privados`: universo estructural mínimo IBEX 35 + PSI, enriquecido progresivamente con señales públicas.

## Validación local

```powershell
$env:PYTHONPATH="scripts"
python scripts/v312/build_intelligence.py
python -m unittest tests/test_v312.py
python scripts/v312/validate_v312.py
node --check assets/v312/intelligence.js
node tests/ui_smoke_v312.js
```

Actualización opcional de contratación pública antes de reconstruir:

```powershell
python scripts/v312/procurement_research.py --profile weekly
python scripts/v312/build_intelligence.py
```

## Automatización

Los workflows diario, semanal y mensual ejecutan `scripts/research_supervisor_v312.py`, amplían investigación pública, actualizan contratación exacta y publican `data/v312/`. Si una fuente temporalmente falla, se conserva la última evidencia válida y se publica el resto de la investigación disponible.
