from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from v317.build_intelligence import build,write_snapshot
def run(root:Path,profile:str='daily',foundation_rc:int=0)->dict[str,Any]:
 started=datetime.now(timezone.utc);result=write_snapshot(build());result['profile']=profile;result['foundation_rc']=foundation_rc;result['started_at']=started.isoformat();result['finished_at']=datetime.now(timezone.utc).isoformat();result['runtime_seconds']=round((datetime.now(timezone.utc)-started).total_seconds(),3)
 path=root/'data/v317/last_run.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result
