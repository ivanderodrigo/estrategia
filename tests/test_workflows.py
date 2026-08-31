
import unittest,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class W(unittest.TestCase):
 def test_refs_exist_and_no_legacy(self):
  for f in (ROOT/'.github/workflows').glob('*.yml'):
   t=f.read_text(encoding='utf-8');self.assertNotRegex(t,r'(data|assets|scripts|config)/v\d+')
   for m in re.findall(r'python ([A-Za-z0-9_./-]+\.py)',t):self.assertTrue((ROOT/m).exists(),f'{f}:{m}')
if __name__=='__main__':unittest.main()
