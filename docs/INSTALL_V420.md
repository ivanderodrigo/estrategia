# Instalación v4.2.0

Baseline requerida: v4.1.0/HF11, working tree limpio.

El instalador:

1. verifica versión y baseline semántica;
2. crea backup transaccional local;
3. instala el motor de shards y Gap Intelligence;
4. migra `intelligence.json` sin pérdida semántica;
5. reconstruye el dataset canónico;
6. ejecuta Preservation Gate, auditorías de evidencia pública, workflow, seguridad y v4.2;
7. ejecuta toda la batería de tests y smoke tests frontend;
8. no hace commit ni push.

No usar Git LFS para este dataset. Los shards son archivos JSON normales y GitHub Pages continúa usando `data/public/`.
