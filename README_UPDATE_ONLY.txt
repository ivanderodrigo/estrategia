WESTCON IBERIA DECISION INTELLIGENCE · UPDATE ONLY v3.17.0

Baseline requerida: v3.16.0 con carpeta .git.

1. Descomprime Westcon_v3.17.0_UPDATE_ONLY.zip fuera del repositorio.
2. Ejecuta:
   python aplicar_v317.py --repo "C:\Users\ivand\Downloads\estrategia"
3. El instalador valida VERSION=3.16.0, copia únicamente los archivos del manifiesto, ejecuta 43 pruebas, valida el publicador automático, los datos y la interfaz.
4. Si falla cualquier comprobación, restaura los archivos anteriores y elimina los nuevos.

No modifica .git, no crea commits y no hace push.
