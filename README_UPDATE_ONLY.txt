WESTCON IBERIA DECISION INTELLIGENCE · UPDATE ONLY v3.15.0

Baseline requerida: v3.14.0 con carpeta .git.

1. Descomprime Westcon_v3.15.0_UPDATE_ONLY.zip fuera del repositorio.
2. Ejecuta:
   python aplicar_v315.py --repo "C:\Users\ivand\Downloads\estrategia"
3. El instalador valida VERSION=3.14.0, copia los 39 archivos del manifiesto, ejecuta 37 pruebas, validación Python y smoke test JavaScript.
4. Si falla cualquier comprobación, restaura los archivos anteriores y elimina los nuevos.

No modifica .git, no crea commits y no hace push.
