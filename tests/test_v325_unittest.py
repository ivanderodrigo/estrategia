import tempfile, unittest, re
from pathlib import Path

class V325Tests(unittest.TestCase):
    def test_installer_contains_portable_backend(self):
        text=(Path(__file__).resolve().parents[1]/"tools/aplicar_v325.py").read_text(encoding="utf-8")
        self.assertIn("V325_WINDOWS_STREAM_COMPAT",text)
        self.assertIn("thread_queue",text)
        self.assertNotIn("selectors.DefaultSelector",text)

    def test_v31_surfaces_legacy_status(self):
        text=(Path(__file__).resolve().parents[1]/"scripts/research_supervisor_v31.py").read_text(encoding="utf-8")
        self.assertIn("legacy {report.get('legacy'",text)
        self.assertIn('"status": "ok" if proc.returncode == 0 else "failed"',text)

    def test_v32_surfaces_foundation(self):
        text=(Path(__file__).resolve().parents[1]/"scripts/research_supervisor_v32.py").read_text(encoding="utf-8")
        self.assertIn("foundation v31=",text)
        self.assertIn('"version":"3.2.6"',text)

    def test_supervisors_compile(self):
        root=Path(__file__).resolve().parents[1]
        for rel in ["scripts/research_supervisor_v31.py","scripts/research_supervisor_v32.py","tools/aplicar_v325.py"]:
            p=root/rel
            compile(p.read_text(encoding="utf-8"),str(p),"exec")

if __name__=="__main__": unittest.main()
