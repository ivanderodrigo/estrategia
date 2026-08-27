#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from v31.atomic_publish import DatasetSnapshot, atomic_write_json
from v31.source_registry import load_registry
from v32.pipeline import run_pipeline
from v32.validate_v32 import validate


def args_parse():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",default="daily",choices=["daily","weekly","monthly"])
    p.add_argument("--max-runtime",type=int,default=720)
    p.add_argument("--v31-share",type=float,default=None)
    p.add_argument("--skip-v31",action="store_true")
    p.add_argument("--skip-legacy",action="store_true",help="Passed to v3.1 when v3.1 is executed")
    return p.parse_args()


def load(path,default):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:return default


def main():
    a=args_parse();started=time.monotonic();snap=DatasetSnapshot(ROOT);snap.create()
    policy=load(ROOT/"config/v32/policy.json",{});direct=load(ROOT/"config/v32/direct_sources.json",{})
    share=a.v31_share if a.v31_share is not None else float((policy.get("v31_budget_share") or {}).get(a.profile,.58))
    v31_seconds=max(90,int(a.max_runtime*share));v32_seconds=max(45,a.max_runtime-v31_seconds-10)
    report={"version":"3.2.6","profile":a.profile,"started_at":datetime.now(timezone.utc).isoformat(),"v31_budget":v31_seconds,"v32_budget":v32_seconds}
    try:
        if not a.skip_v31:
            cmd=[sys.executable,str(ROOT/"scripts/research_supervisor_v31.py"),"--profile",a.profile,"--max-runtime",str(v31_seconds)]
            if a.skip_legacy:cmd.append("--skip-legacy")
            print(f"v3.2.6 foundation · running v3.1 evidence discovery for up to {v31_seconds}s",flush=True)
            proc=subprocess.run(cmd,cwd=ROOT,timeout=v31_seconds+30)
            report["v31_rc"]=proc.returncode
            v31_last=load(ROOT/"data/v31/last_run.json",{})
            legacy_info=v31_last.get("legacy",{}) if isinstance(v31_last,dict) else {}
            report["foundation"]={
                "v31_status": (v31_last.get("status") if isinstance(v31_last,dict) else None) or ("ok" if proc.returncode==0 else "failed"),
                "legacy_status": legacy_info.get("status") or ("ok" if legacy_info.get("returncode")==0 else ("failed" if legacy_info.get("returncode") is not None else "unknown")),
                "legacy_returncode": legacy_info.get("returncode"),
            }
            if proc.returncode!=0:print("v3.2.6 warning · v3.1 returned non-zero; preserving available evidence and continuing",flush=True)
        else:
            report["foundation"]={"v31_status":"skipped","legacy_status":"skipped","legacy_returncode":None}
        registry=load_registry(ROOT/"config/v31/source_registry.json")
        print(f"v3.2.6 evidence & event intelligence · {len(registry)} registered sources · direct connectors + event graph · budget {v32_seconds}s",flush=True)
        result=run_pipeline(ROOT,registry,policy,direct,profile=a.profile,runtime_seconds=v32_seconds)
        errors=validate(ROOT)
        if errors:raise RuntimeError("; ".join(errors[:12]))
        snap.write_release_manifest();report.update(result);report["status"]="published";report["finished_at"]=datetime.now(timezone.utc).isoformat();report["runtime_seconds"]=round(time.monotonic()-started,1)
        atomic_write_json(ROOT/"data/v32/last_run.json",report)
        ds=result.get("direct_stats",{})
        parts=[]
        for k,v in ds.items():
            if k=="generic_feeds":
                parts.append(f"{k} rows {v.get('rows',0)} feeds {v.get('successful_sources',0)}/{v.get('attempted_sources',0)} err {v.get('failed_sources',v.get('failed',0))} nofeed {v.get('no_feed_sources',0)}")
            else:
                ok=v.get('successful')
                ok_txt=f" ok {ok}/{v.get('attempted',0)}" if ok is not None else ""
                err=(v.get('errors') or [v.get('error')])
                err=next((str(x) for x in err if x),"")
                cache_txt=f" cache {v.get('cached',0)}" if v.get('cached') is not None else ""
                parts.append(f"{k} rows {v.get('rows',0)}{ok_txt} fail {v.get('failed',0)}{cache_txt}"+(f" err {err[:120]}" if err else ""))
        src_txt=", ".join(parts) or "none"
        b=result.get("briefing",{}).get("headline_metrics",{})
        print(
            f"v3.2.6 published · foundation v31={report.get('foundation',{}).get('v31_status','unknown')} legacy={report.get('foundation',{}).get('legacy_status','unknown')} · "
            f"events {result.get('events',0)} · decisions {result.get('decisions',0)} · graph {result.get('nodes',0)} nodes/{result.get('edges',0)} edges · "
            f"direct rows {result.get('direct_rows',0)}/{result.get('direct_raw_rows',0)} (dedup {result.get('direct_deduplicated_rows',0)}) · Iberia events {b.get('iberia_events',0)} · opportunities {b.get('opportunities',0)} · threats {b.get('threats',0)} · high-econ {b.get('high_economic_potential',0)} medium-econ {b.get('medium_economic_potential',0)} max-econ {b.get('max_economic_priority_score',0)} · competitive {result.get('competitive_high',0)} high/{result.get('competitive_medium',0)} medium ({result.get('competitive_entities',0)} entities) · whitespace {result.get('whitespace_shortlist',0)} shortlist/{result.get('whitespace_candidates',0)} research · sources [{src_txt}]",
            flush=True
        )
        return 0
    except Exception as exc:
        print(f"v3.2.6 rollback: {exc}",file=sys.stderr,flush=True);snap.restore();report["status"]="rolled_back";report["error"]=repr(exc)
        try:atomic_write_json(ROOT/".v32_state/last_failure.json",report)
        except Exception:pass
        return 1

if __name__=="__main__":raise SystemExit(main())
