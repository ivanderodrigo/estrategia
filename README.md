# Westcon Iberia Business Intelligence v3.13.0

Release centrada en **cobertura de evidencia, investigación adaptativa y una UX de trazabilidad deliberada**.

## Qué cambia

- **Mayoristas validados positivamente.** Ya no basta con que una empresa aparezca relacionada con fabricantes: debe existir evidencia explícita de que actúa como distribuidor, mayorista o VAD. Fabricantes como Akamai, Cradlepoint, Splunk, Stratus/Penguin, Noname o Forescout no pueden entrar en la tabla por inferencia débil.
- **Portfolio Westcon saneado.** `westcon_fit` solo admite nombres presentes en el portfolio activo del dataset; Forescout queda fuera.
- **Grandes cuentas completas.** La cobertura mínima de clientes privados pasa a ser IBEX 35 completo en España y PSI completo en Portugal.
- **Más contratación pública y mejor trazabilidad.** Cada fila publicada debe apuntar al anuncio/expediente oficial concreto. La v3.13 incorpora un snapshot amplio y un collector dinámico TED + PLACSP.
- **Más integradores y más relaciones por fabricante.** El grafo se alimenta en ambas direcciones: fabricante → partner locator/directorios/casos/premios/certificaciones y integrador → portfolio/alianzas/casos/certificaciones. La relación solo se publica con evidencia.
- **Tarjetas por clic, no por hover.** La trazabilidad se abre solo cuando el usuario la solicita y permanece estable durante lectura y scroll.
- **Gap engine real.** Cada celda vacía/antigua/débil del dataset actual alimenta automáticamente búsquedas específicas; ya no se reutiliza un contador antiguo de gaps.
- **Investigación de perfiles oficiales.** Servicios, capacidades, verticales, certificaciones, casos y empleo se extraen de páginas oficiales de integradores/mayoristas aunque no mencionen un vendor Westcon.
- **Grandes cuentas en profundidad.** Los 51 dominios corporativos IBEX 35 + PSI entran en el barrido oficial.
- **Investigación más profunda.** Daily hasta 320 queries; deep 900 y 3.200 páginas de ecosistema; exhaustive 1.600 y 6.000 páginas, con checkpoint/resume y publicación parcial segura.

## Principios de clasificación

1. `Mayoristas`: positive-validation-first.
2. `Fabricantes`: portfolio Westcon activo + contexto competitivo; no se convierten en mayoristas por vender directa o indirectamente.
3. `Integradores`: entidad validada + relaciones fabricante↔integrador evidenciadas y bidireccionales.
4. `Clientes públicos`: expediente concreto, nunca una portada genérica del portal.
5. `Clientes privados`: universo estructural mínimo IBEX 35 + PSI, enriquecido progresivamente con señales públicas.

## Validación local

```powershell
$env:PYTHONPATH="scripts"
python scripts/v313/build_intelligence.py
python -m unittest tests/test_v313.py
python scripts/v313/validate_v313.py
node --check assets/v313/intelligence.js
node tests/ui_smoke_v313.js
```

Actualización opcional de contratación pública antes de reconstruir:

```powershell
python scripts/v313/procurement_research.py --profile weekly
python scripts/v313/build_intelligence.py
```

## Automatización

Los workflows diario, semanal y mensual ejecutan `scripts/research_supervisor_v313.py`, amplían investigación pública, actualizan contratación exacta y publican `data/v313/`. Si una fuente temporalmente falla, se conserva la última evidencia válida y se publica el resto de la investigación disponible.
