#!/usr/bin/env python3
from __future__ import annotations
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from v33.pipeline import run
from v33.common import load_json
from v33.validate_v33 import validate

def ap():
 p=argparse.ArgumentParser();p.add_argument("--profile",default="daily",choices=["daily","weekly","monthly"]);p.add_argument("--max-runtime",type=int,default=720);p.add_argument("--skip-v32",action="store_true");return p.parse_args()

def main():
 a=ap();policy=load_json(ROOT/"config/v33/policy.json",{});share=float((policy.get("runtime_share") or {}).get(a.profile,.22));v33=max(60,int(a.max_runtime*share));v32=max(90,a.max_runtime-v33-10)
 if not a.skip_v32:
  print(f"v3.3.3a foundation · running v3.2 for up to {v32}s",flush=True)
  p=subprocess.run([sys.executable,str(ROOT/"scripts/research_supervisor_v32.py"),"--profile",a.profile,"--max-runtime",str(v32)],cwd=ROOT,timeout=v32+45)
  if p.returncode!=0:print("v3.3.3a warning · v3.2 returned non-zero; continuing with last-good datasets",flush=True)
 print(f"v3.3.3a ecosystem intelligence · traceable identity + structural tiers + comparable movements · budget {v33}s",flush=True)
 r=run(ROOT,a.profile,policy,v33);errors=validate(ROOT)
 if errors:
  print('v3.3.3a validation failed · '+ '; '.join(errors[:10]),file=sys.stderr,flush=True);return 1
 ts=r.get('targeted_stats',{});delta=r.get('coverage_delta');delta_txt='n/a' if delta is None else f"{delta:+.1f}pp"
 tiers=r.get('tier_distribution') or {}
 print(
   f"v3.3.3a published · profiles {r['profiles']} ({r['distributors']} mayoristas/{r['integrators']} integradores; {r.get('consolidated_source_variants',0)} variantes de fuente consolidadas en {r.get('groups_with_variants',0)} grupos) · "
   f"scope conflicts {r.get('name_scope_conflicts_resolved',0)} resolved/{r.get('unresolved_name_scope_conflicts',0)} unresolved · tiers T1 {tiers.get('T1',0)}/T2 {tiers.get('T2',0)}/T3 {tiers.get('T3',0)} · coverage {r.get('average_profile_coverage')}% ({delta_txt}) target {r.get('average_coverage_target')}% mean-delta {r.get('difference_between_averages')}pp knowledge-debt {r.get('average_coverage_gap')}pp · "
   f"evidence +{r.get('new_targeted_evidence',0)}/{r.get('targeted_evidence',0)} acumulada · queries {ts.get('attempted_queries',0)}/{ts.get('planned_queries',0)} · entities {ts.get('entities_touched',0)}/{ts.get('unique_entities_planned',0)} · pair checks {ts.get('pair_verification_queries',0)} · "
   f"integrator relations {r.get('integrator_confirmed',0)} confirmed/{r.get('integrator_probable',0)} probable/{r.get('integrator_whitespace',0)} research · "
   f"distributor relations {r.get('distributor_confirmed',0)} confirmed/{r.get('distributor_probable',0)} probable · movement {r.get('relationship_changes',0)} changes/{r.get('uncertainty_resolved',0)} resolved · verification queue {r.get('verification_queue',0)} · errors {len(ts.get('errors',[]))}",flush=True)
 return 0
if __name__=="__main__":raise SystemExit(main())
