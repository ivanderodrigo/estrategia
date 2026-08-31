#!/usr/bin/env python3
"""Transactional v3.15.0 -> v3.16.0 updater. No git mutations."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PACKAGE=HERE if (HERE/'config/v316/update_manifest.json').is_file() else HERE.parent
MANIFEST=PACKAGE/'config/v316/update_manifest.json'
def parse_args():
 p=argparse.ArgumentParser(description='Aplica Westcon Decision Intelligence v3.16.0 sobre una copia v3.15.0');p.add_argument('--repo',required=True,help='Ruta a la raíz del repositorio v3.15.0');return p.parse_args()
def digest(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def run_check(command:list[str],repo:Path)->None:
 print('+ '+' '.join(command),flush=True);subprocess.run(command,cwd=repo,check=True)
def main()->int:
 args=parse_args();repo=Path(args.repo).expanduser().resolve()
 if not repo.is_dir():print(f'ERROR: no existe el repositorio: {repo}',file=sys.stderr);return 2
 if not (repo/'.git').exists():print('ERROR: la ruta no contiene .git; se cancela para evitar actualizar una carpeta equivocada.',file=sys.stderr);return 2
 version=(repo/'VERSION').read_text(encoding='utf-8').strip() if (repo/'VERSION').is_file() else ''
 if version!='3.15.0':print(f'ERROR: base incompatible. Se esperaba VERSION 3.15.0 y se encontró {version or "sin VERSION"}.',file=sys.stderr);return 3
 if not MANIFEST.is_file():print('ERROR: falta config/v316/update_manifest.json en el paquete.',file=sys.stderr);return 4
 manifest=json.loads(MANIFEST.read_text(encoding='utf-8'));files=[str(x) for x in manifest.get('files') or []]
 if not files or any(Path(x).is_absolute() or '..' in Path(x).parts for x in files):print('ERROR: manifiesto vacío o inseguro.',file=sys.stderr);return 4
 missing=[rel for rel in files if not (PACKAGE/rel).is_file()]
 if missing:print('ERROR: faltan archivos del paquete: '+', '.join(missing[:10]),file=sys.stderr);return 4
 git_before=digest(repo/'.git/HEAD') if (repo/'.git/HEAD').is_file() else None
 backup=Path(tempfile.mkdtemp(prefix='westcon_v316_rollback_'));existing=[];created=[]
 try:
  for rel in files:
   src=PACKAGE/rel;dst=repo/rel
   if dst.exists():
    backup_dst=backup/rel;backup_dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,backup_dst);existing.append(rel)
   else:created.append(rel)
   dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name(dst.name+'.v316.tmp');shutil.copy2(src,tmp);os.replace(tmp,dst)
  run_check([sys.executable,'-m','unittest','tests/test_v316.py','-v'],repo)
  run_check([sys.executable,'scripts/v316/validate_v316.py'],repo)
  if shutil.which('node'):
   run_check(['node','--check','assets/v316/intelligence.js'],repo);run_check(['node','tests/ui_smoke_v316.js'],repo)
  if git_before and digest(repo/'.git/HEAD')!=git_before:raise RuntimeError('.git/HEAD cambió durante la instalación')
 except Exception as exc:
  print(f'ERROR: la validación falló; revirtiendo: {exc}',file=sys.stderr,flush=True)
  for rel in reversed(created):
   target=repo/rel
   if target.is_file() or target.is_symlink():target.unlink()
  for rel in existing:
   src=backup/rel;dst=repo/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
  shutil.rmtree(backup,ignore_errors=True);print('ROLLBACK COMPLETADO. El repositorio vuelve al estado anterior.',file=sys.stderr);return 5
 shutil.rmtree(backup,ignore_errors=True);print(f'v3.16.0 instalada y validada: {len(files)} archivos. .git preservado. No se ha creado commit ni push.');return 0
if __name__=='__main__':raise SystemExit(main())
