from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
VERSION = ROOT / "VERSION"
CSS = '  <link rel="stylesheet" href="assets/v327/ecosystem-tables.css?v=3.2.7">'
JS = '  <script src="assets/v327/ecosystem-tables.js?v=3.2.7" defer></script>'

def main():
    if not INDEX.exists():
        raise SystemExit("ERROR: no existe index.html en la raíz del proyecto")
    text = INDEX.read_text(encoding="utf-8")
    if "assets/v327/ecosystem-tables.css" not in text:
        marker = '</head>'
        text = text.replace(marker, CSS + '\n' + marker, 1)
    if "assets/v327/ecosystem-tables.js" not in text:
        marker = '</body>'
        text = text.replace(marker, JS + '\n' + marker, 1)
    INDEX.write_text(text, encoding="utf-8")
    VERSION.write_text("3.2.7\n", encoding="utf-8")
    print("v3.2.7 aplicada: Mayoristas e Integradores pasan a tablas nativas comparables con Fabricantes.")
    print("No cambia el motor de research v3.2.6; solo la capa de visualización/BI.")
    print("Validación: node --check assets/v327/ecosystem-tables.js")

if __name__ == "__main__":
    main()
