"""HF6 R23: final normalization must precede strict support reconciliation."""
import unittest
from pathlib import Path

class FinalAccreditedSupportOrdering(unittest.TestCase):
    def test_final_reconciliation_is_after_last_normalize(self):
        code = (Path(__file__).resolve().parents[1] / 'engine/pipeline.py').read_text(encoding='utf-8')
        build = code[code.index('def run()'):]
        assert 'final_support_reconciliation = restore_accredited_support(data, preservation_source)' in build
        final_normalize = build.rfind('    normalize_fields(data)')
        final_restore = build.index('    final_support_reconciliation = restore_accredited_support(data, preservation_source)')
        self.assertLess(final_normalize, final_restore)
        self.assertIn('"accredited_support_final": final_support_reconciliation', build)
        self.assertLess(final_restore, build.index('    preservation_after = preservation_snapshot(data, graph)'))

if __name__ == '__main__':
    unittest.main()
