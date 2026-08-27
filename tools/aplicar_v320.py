#!/usr/bin/env python3
from __future__ import annotations
import re,shutil
from datetime import datetime
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1];REPO=Path.cwd().resolve()
DIRS=["scripts/v32","config/v32","assets/v32"]
FILES=["scripts/research_supervisor_v32.py","tests/test_v320_unittest.py","README_V320.md"]

def same(a,b):
 try:return a.resolve()==b.resolve()
 except Exception:return False

def copy():
 changed=0
 for rel in DIRS:
  src=PACKAGE/rel;dst=REPO/rel
  if same(src,dst):continue
  if dst.exists():shutil.rmtree(dst)
  dst.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(src,dst);changed+=1
 for rel in FILES:
  src=PACKAGE/rel;dst=REPO/rel
  if same(src,dst):continue
  dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists():
   bak=dst.with_suffix(dst.suffix+'.v315.bak')
   if not bak.exists():shutil.copy2(dst,bak)
  shutil.copy2(src,dst);changed+=1
 return changed

def frontend():
 p=REPO/'index.html'
 if not p.exists():return 'index.html no encontrado; frontend omitido'
 t=p.read_text(encoding='utf-8');bak=p.with_suffix(f'.html.v315-{datetime.now().strftime("%Y%m%d%H%M%S")}.bak')
 if not bak.exists():shutil.copy2(p,bak)
 css='<link rel="stylesheet" href="assets/v32/decision-intelligence.css?v=3.2.0">';js='<script src="assets/v32/decision-intelligence.js?v=3.2.0" defer></script>'
 if 'assets/v32/decision-intelligence.css' not in t:t=re.sub(r'</head>',f'  {css}\n</head>',t,count=1,flags=re.I)
 if 'assets/v32/decision-intelligence.js' not in t:t=re.sub(r'</body>',f'  {js}\n</body>',t,count=1,flags=re.I)
 p.write_text(t,encoding='utf-8');return 'frontend v3.2 inyectado'

def workflows():
 d=REPO/'.github/workflows';changed=[]
 if not d.exists():return changed
 for p in list(d.glob('*.yml'))+list(d.glob('*.yaml')):
  t=p.read_text(encoding='utf-8');n=t.replace('scripts/research_supervisor_v31.py','scripts/research_supervisor_v32.py')
  if n!=t:
   bak=p.with_suffix(p.suffix+'.v315.bak')
   if not bak.exists():shutil.copy2(p,bak)
   p.write_text(n,encoding='utf-8');changed.append(p.name)
 return changed

def gitignore():
 p=REPO/'.gitignore';t=p.read_text(encoding='utf-8') if p.exists() else ''
 for line in ['.v32_state/','*.v315.bak','*.v315-*.bak']:
  if line not in t.splitlines():t+=("\n" if t and not t.endswith("\n") else "")+line+"\n"
 p.write_text(t,encoding='utf-8')

def main():
 if not (REPO/'.git').exists():print('ERROR: ejecuta desde la raíz del repo (donde está .git).');return 2
 n=copy();(REPO/'VERSION').write_text('3.2.0\n',encoding='utf-8');gitignore();print(frontend());print('workflows:',', '.join(workflows()) or 'ninguno');print(f'v3.2.0 aplicada · {n} bloques/archivos actualizados.');print('Test: python tests/test_v320_unittest.py');print('Prueba motor nuevo: python scripts/research_supervisor_v32.py --profile daily --max-runtime 180 --skip-v31');print('Prueba integral después: python scripts/research_supervisor_v32.py --profile daily --max-runtime 720');return 0
if __name__=='__main__':raise SystemExit(main())
