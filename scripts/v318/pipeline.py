from pathlib import Path
from v318.build_intelligence import build,write_snapshot
def run(root:Path,profile='daily',foundation_rc=0):
 r=write_snapshot(build());r['profile']=profile;r['foundation_rc']=foundation_rc;return r
