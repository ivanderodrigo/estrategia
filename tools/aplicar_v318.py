#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
BASELINE='3.17.0';TARGET='3.18.0'
def sha(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser(description='Instalador seguro UPDATE_ONLY Westcon Decision Intelligence v3.18.0');ap.add_argument('target',nargs='?',default='.');ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
 here=Path(__file__).resolve().parent;payload=here/'payload';manifest_path=here/'manifest.json'
 if a.self_test:
  assert BASELINE=='3.17.0' and TARGET=='3.18.0';print('INSTALLER SELF-TEST · PASS');return 0
 if not payload.is_dir() or not manifest_path.is_file():raise SystemExit('Falta payload/ o manifest.json junto al instalador.')
 target=Path(a.target).resolve();version=target/'VERSION'
 if not version.is_file() or version.read_text(encoding='utf-8').strip()!=BASELINE:raise SystemExit(f'ABORTADO: baseline incompatible. Se requiere VERSION {BASELINE}.')
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 # Verificar solo archivos baseline que se van a sustituir; no tocar datos ajenos.
 for rel,expected in manifest.get('baseline_hashes',{}).items():
  p=target/rel
  if not p.is_file() or sha(p)!=expected:raise SystemExit(f'ABORTADO: {rel} no coincide con la baseline adjunta. No se ha modificado nada.')
 backup=Path(tempfile.mkdtemp(prefix='westcon-v318-backup-'));copied=[]
 try:
  for rel in manifest['files']:
   src=payload/rel;dst=target/rel
   if dst.exists():
    b=backup/rel;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,b)
   dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);copied.append(rel)
  cmds=[[sys.executable,'-m','unittest','tests/test_v318.py'],[sys.executable,'scripts/v318/validate_v318.py'],[sys.executable,'scripts/v318/audit_workflows.py']]
  for cmd in cmds:
   r=subprocess.run(cmd,cwd=target)
   if r.returncode:raise RuntimeError('Falla validación: '+' '.join(cmd))
 except Exception as exc:
  for rel in copied:
   dst=target/rel;b=backup/rel
   if b.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(b,dst)
   elif dst.exists():dst.unlink()
  raise SystemExit(f'ABORTADO Y REVERTIDO: {exc}')
 finally:shutil.rmtree(backup,ignore_errors=True)
 print(f'UPDATE_ONLY instalado correctamente: {BASELINE} -> {TARGET}. .git no se ha tocado; no se ha hecho commit ni push.')
 return 0
if __name__=='__main__':raise SystemExit(main())
