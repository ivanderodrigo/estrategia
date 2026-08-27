from pathlib import Path
from datetime import datetime
import re,shutil
ROOT=Path(__file__).resolve().parents[1];INDEX=ROOT/'index.html';VERSION=ROOT/'VERSION';GI=ROOT/'.gitignore'
CSS=['  <link rel="stylesheet" href="assets/v331/ecosystem-intelligence.css?v=3.3.1">','  <link rel="stylesheet" href="assets/v331/executive-output.css?v=3.3.1">']
JS='  <script src="assets/v331/ecosystem-intelligence.js?v=3.3.1" defer></script>'

def backup(path):
 if not path.exists():return
 stamp=datetime.now().strftime('%Y%m%d%H%M%S');d=ROOT/'.local-backups'/f'v331-{stamp}';d.mkdir(parents=True,exist_ok=True);rel=path.relative_to(ROOT);dst=d/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)

def patch_workflow(p):
 if not p.exists():return False
 t=p.read_text(encoding='utf-8');old=t;backup(p)
 # v3.3 sigue siendo el orquestador. Si el repo aún apunta a v32, se actualiza.
 t=t.replace('scripts/research_supervisor_v32.py --profile','scripts/research_supervisor_v33.py --profile')
 if 'data/v33/' not in t:
  lines=t.splitlines();out=[]
  for line in lines:
   if 'git add ' in line and 'data/v31/' in line:line=line.rstrip()+' data/v33/'
   out.append(line)
  t='\n'.join(out)+'\n'
 if t!=old:p.write_text(t,encoding='utf-8');return True
 return False

def main():
 if not INDEX.exists():raise SystemExit('ERROR: no existe index.html en la raíz del proyecto')
 backup(INDEX);text=INDEX.read_text(encoding='utf-8')
 # Retira referencias v3.3.0/v3.2.7 para evitar doble renderizado y caché antiguo.
 text=re.sub(r'\s*<link[^>]+assets/v330/ecosystem-intelligence\.css[^>]*>','',text)
 text=re.sub(r'\s*<link[^>]+assets/v330/executive-output\.css[^>]*>','',text)
 text=re.sub(r'\s*<script[^>]+assets/v330/ecosystem-intelligence\.js[^>]*></script>','',text)
 for css in CSS:
  href=re.search(r'href="([^"]+)',css).group(1).split('?')[0]
  if href not in text:text=text.replace('</head>',css+'\n</head>',1)
 if 'assets/v331/ecosystem-intelligence.js' not in text:text=text.replace('</body>',JS+'\n</body>',1)
 INDEX.write_text(text,encoding='utf-8');VERSION.write_text('3.3.1\n',encoding='utf-8')
 if GI.exists():
  g=GI.read_text(encoding='utf-8')
  if '.local-backups/' not in g:GI.write_text(g.rstrip()+'\n\n# Backups locales de instaladores\n.local-backups/\n',encoding='utf-8')
 changed=[]
 for name in ['research-daily.yml','research-weekly.yml','research-monthly.yml']:
  if patch_workflow(ROOT/'.github/workflows'/name):changed.append(name)
 print('v3.3.1 aplicada: investigación adaptativa de gaps + verificación de relaciones + cobertura/calidad + BI ampliada.')
 print('workflows actualizados: '+(', '.join(changed) if changed else 'ninguno / ya estaban en v3.3'))
 print('Prueba: python scripts/research_supervisor_v33.py --profile daily --max-runtime 180 --skip-v32')
if __name__=='__main__':main()
