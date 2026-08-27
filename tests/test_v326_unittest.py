#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v326', HERE/'tools'/'aplicar_v326.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

VALIDATE = """from pathlib import Path\nROOT=Path('.')\ndef main():\n    for wf in ['.github/workflows/research-daily.yml']:\n        text=(ROOT/wf).read_text(encoding='utf-8')\n        assert 'research_supervisor.py' in text and 'upload-artifact@v4' in text, f'Workflow sin supervisor/diagnóstico: {wf}'\n    for script in ['research_supervisor.py','configure_updates.py','schedule_guard.py','test_schedule.py']:\n        assert (ROOT/'scripts'/script).exists()\n"""

WORKFLOW = """jobs:\n  research:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Preflight\n        run: python -m py_compile scripts/research.py scripts/research_supervisor_v32.py scripts/validate.py\n      - name: Investigacion\n        run: python scripts/research_supervisor_v32.py --profile daily --max-runtime 720\n      - name: Diagnostico\n        uses: actions/upload-artifact@v4\n        with:\n          path: |\n            diagnostics/*.log\n            data/research_queue.json\n      - name: Guardar\n        run: |\n          git add data/research.latest.json data/history/\n          git diff --cached --quiet || git commit -m test\n"""

class TestV326(unittest.TestCase):
    def test_validate_accepts_hierarchy_and_persistence(self):
        out, changed = mod.patch_validate_text(VALIDATE)
        self.assertTrue(changed)
        self.assertIn('research_supervisor_v32.py', out)
        self.assertIn('data/v31/', out)
        self.assertIn('data/v32/', out)
        compile(out,'validate.py','exec')

    def test_workflow_persists_v31_v32_and_compiles_chain(self):
        out, changed = mod.patch_workflow_text(WORKFLOW)
        self.assertTrue(changed)
        self.assertIn('data/v31/', out)
        self.assertIn('data/v32/', out)
        self.assertIn('scripts/research_supervisor.py', out)
        self.assertIn('scripts/research_supervisor_v31.py', out)
        self.assertIn('scripts/research_supervisor_v32.py', out)
        self.assertIn('git add data/v31/ data/v32/', out)

    def test_workflow_patch_is_idempotent(self):
        one, _ = mod.patch_workflow_text(WORKFLOW)
        two, changed = mod.patch_workflow_text(one)
        self.assertFalse(changed)
        self.assertEqual(one, two)

    def test_v32_version_label(self):
        src='report={"version":"3.2.5"}\nprint("v3.2.5 published")\n'
        out, changed=mod.patch_v32_version_text(src)
        self.assertTrue(changed)
        self.assertIn('3.2.6',out)
        self.assertNotIn('v3.2.5 published',out)

if __name__=='__main__': unittest.main()
