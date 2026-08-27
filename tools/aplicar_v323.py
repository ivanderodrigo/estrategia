#!/usr/bin/env python3
from __future__ import annotations
import shutil
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
REPO=Path.cwd().resolve()
FILES=[
    'scripts/research_supervisor_v32.py',
    'scripts/v32/direct_sources.py',
    'scripts/v32/event_intelligence.py',
    'scripts/v32/knowledge_graph.py',
    'scripts/v32/decision_engine.py',
    'scripts/v32/pipeline.py',
    'scripts/v32/market_intelligence.py',
    'config/v32/direct_sources.json',
    'config/v32/policy.json',
    'tests/test_v323_unittest.py',
    'README_V323.md',
]

def same(a:Path,b:Path)->bool:
    try:return a.resolve()==b.resolve()
    except Exception:return False

def main():
    if not (REPO/'.git').exists():
        print('ERROR: ejecuta desde la raíz del repo (donde está .git).')
        return 2
    changed=0
    for rel in FILES:
        src=PACKAGE/rel;dst=REPO/rel
        if not src.exists():continue
        if same(src,dst):continue
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);changed+=1
    (REPO/'VERSION').write_text('3.2.3\n',encoding='utf-8')
    print(f'v3.2.3 aplicada · {changed} archivos copiados.')
    print('Tests: python tests/test_v320_unittest.py ; python tests/test_v321_unittest.py ; python tests/test_v322_unittest.py ; python tests/test_v323_unittest.py')
    print('Prueba: python scripts/research_supervisor_v32.py --profile daily --max-runtime 180 --skip-v31')
    return 0

if __name__=='__main__':raise SystemExit(main())
