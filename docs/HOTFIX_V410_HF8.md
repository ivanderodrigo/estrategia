# Westcon Decision Intelligence v4.1.0-HF8 — Public Evidence Memory

HF8 completes the public-evidence migration introduced in HF7.

## Contract

- PPT, portfolio and historical/internal lineage are **research clues only** (`RESEARCH_SEED`).
- External facts are accredited only by current public evidence.
- A clue is never silently deleted: HF8 persists it in an internal `research_seed_registry`.
- If the same value survives but lacks current public evidence, the clue remains actionable as
  `Pendiente de validación pública`.
- `Por investigar` is reserved for genuinely unknown/open research gaps.
- The legacy quality gate receives a compatibility copy of the gap labels only after HF8 validates
  the richer state contract itself; persisted data keeps the differentiated states.
- The semantic Preservation Gate remains strict for entities, external values, accredited support,
  graph relations and research-memory claims.

## Safety

The installer is transactional. Any failure restores the exact pre-install state. It performs no
commit and no push.
