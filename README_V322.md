# Westcon Iberia Decision Intelligence v3.2.2

Hotfix de precisión posterior a la auditoría real de v3.2.1.

## Correcciones principales

- Matching de entidades con límites de palabra: `Atos` ya no coincide con `contratos`, ni siglas cortas con códigos aleatorios.
- Contratación pública estructurada prevalece sobre semántica textual: `aquisição/adquisición` de bienes públicos ya no se clasifica como M&A.
- Se separan `procurement_notice` (licitación abierta/señal de demanda) y `procurement_award` (adjudicación ya realizada).
- TED y PLACSP filtran contratación tecnológica por CPV y vocabulario IT/cyber/network/cloud/software; se elimina ruido de ascensores, farmacia, obras, seguros, etc.
- Las licitaciones tecnológicas sin adjudicatario conocido se mantienen como señal de mercado, sin atribuirlas artificialmente a Atos/MCR/u otro integrador.
- `ma_rumor` distingue negociaciones/rumores de una adquisición cerrada.
- `unknown` deja de contaminar `events.json`: se conserva en `unclassified_candidates.json` para investigación posterior.
- `priority` P1/P2/P3/P4 en decisiones; fuentes y número de fuentes quedan visibles.
- `sources`/`source_count` se exponen además de `evidence_sources`.
- Knowledge Graph incluye etiquetas humanas y relaciones de procurement:
  - `Buyer -> PUBLISHED_TECH_TENDER -> Technology`
  - `Buyer -> AWARDED_CONTRACT_TO -> Winner`
- `technology_domains` se amplía y se expone también como `technologies`.
- Salud de fuentes queda aplanada en `source_health.json` para auditoría fácil.
- Amenazas de distribución/expansión competitiva se interpretan en una capa posterior, no como tipo genérico `competitive`.

## Validación local

La suite heredada v3.2.0 + v3.2.1 y los 14 tests de v3.2.2 pasan en el paquete de desarrollo.

## Instalación

Copiar el contenido sobre el repositorio sin borrar `.git`, `.venv` ni `data`, reemplazando archivos coincidentes. Desde la raíz:

```powershell
python tools/aplicar_v322.py
Get-Content VERSION
python tests/test_v320_unittest.py
python tests/test_v321_unittest.py
python tests/test_v322_unittest.py
python scripts/research_supervisor_v32.py --profile daily --max-runtime 180 --skip-v31
```

No hacer push hasta revisar la salida y una muestra de decisiones/eventos.
