from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    (ROOT/"VERSION").write_text("3.3.3a\n",encoding="utf-8")
    print("v3.3.3a aplicada: prioridad geográfica explícita en el nombre + conflictos nombre-ámbito trazables y validados.")
    print("Prueba: python tests/test_v333a_unittest.py")
    print("Después: python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32")
if __name__=="__main__": main()
