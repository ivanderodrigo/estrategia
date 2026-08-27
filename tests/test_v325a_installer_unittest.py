import ast
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "aplicar_v325.py"

spec = importlib.util.spec_from_file_location("v325_installer", INSTALLER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class InstallerASTTests(unittest.TestCase):
    def test_finds_multiline_signature(self):
        text = '''import os\n\ndef before():\n    return 1\n\ndef run_streamed(\n    command,\n    env,\n    max_runtime,\n    log_path,\n    profile,\n):\n    return 7, {}\n\ndef after():\n    return 2\n'''
        start, end = mod._find_function_span(text, "run_streamed")
        block = text[start:end]
        self.assertIn("def run_streamed(", block)
        self.assertIn("return 7", block)
        self.assertNotIn("def after", block)

    def test_finds_decorated_function(self):
        text = '''def deco(f):\n    return f\n\n@deco\ndef run_streamed(\n    command, env, max_runtime, log_path, profile\n):\n    return 0, {}\n'''
        start, end = mod._find_function_span(text, "run_streamed")
        self.assertTrue(text[start:end].startswith("@deco"))

    def test_replacement_compiles(self):
        compile(mod.REPLACEMENT, "replacement", "exec")

    def test_missing_function_is_non_destructive(self):
        with self.assertRaises(SystemExit):
            mod._find_function_span("def other():\n    pass\n", "run_streamed")

if __name__ == "__main__":
    unittest.main()
