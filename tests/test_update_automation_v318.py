import subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestInstaller(unittest.TestCase):
 def test_installer_selftest(self):
  r=subprocess.run([sys.executable,str(ROOT/'tools/aplicar_v318.py'),'--self-test'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('PASS',r.stdout)
if __name__=='__main__':unittest.main()
