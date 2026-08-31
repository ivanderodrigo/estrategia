import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class EncodingSafety(unittest.TestCase):
    def test_text_file_operations_declare_encoding(self):
        offenders=[]
        for path in list((ROOT/'engine').rglob('*.py')) + list((ROOT/'scripts').rglob('*.py')) + list((ROOT/'tests').rglob('*.py')):
            if path.name == self.__class__.__module__.split('.')[-1] + '.py':
                pass
            tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'read_text','write_text'}:
                    if not any(k.arg == 'encoding' for k in node.keywords):
                        offenders.append(f"{path.relative_to(ROOT)}:{getattr(node,'lineno','?')}:{node.func.attr}")
        self.assertFalse(offenders, 'Text I/O sin encoding explícito (rompe Windows cp1252): '+', '.join(offenders))

if __name__ == '__main__': unittest.main()
