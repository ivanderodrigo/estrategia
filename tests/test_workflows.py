import unittest,re
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
class W(unittest.TestCase):
 def test_workflows_parse_and_refs_exist(self):
  for f in (ROOT/'.github/workflows').glob('*.yml'):
   t=f.read_text(encoding='utf-8');self.assertIsInstance(yaml.safe_load(t),dict);self.assertNotRegex(t,r'(data|assets|scripts|config)/v\d+');self.assertNotIn('actions/checkout@v4',t)
   for m in re.findall(r'python ([A-Za-z0-9_./-]+\.py)',t):self.assertTrue((ROOT/m).exists(),f'{f}:{m}')
 def test_research_workflows_share_lock(self):
  for name in ['daily','weekly','monthly']:
   t=(ROOT/f'.github/workflows/research-{name}.yml').read_text(encoding='utf-8');self.assertIn('group: westcon-intelligence-research',t);self.assertIn('contents: write',t)
if __name__=='__main__':unittest.main()
