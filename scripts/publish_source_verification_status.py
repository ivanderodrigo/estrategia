#!/usr/bin/env python3
"""Publish bounded verification telemetry; never turn source checks into proof."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCHEDULED_NAMES = (
    "Westcon Intelligence Daily",
    "Westcon Intelligence Weekly",
    "Westcon Intelligence Monthly",
    "Historical Source Diligence",
    "Westcon Source Verification",
)


def scheduled_health(runs):
    """Summarize actual scheduled Actions runs, never infer success from cron."""
    records = (runs or {}).get("workflow_runs") or []
    output = {}
    for name in SCHEDULED_NAMES:
        matching = sorted(
            [x for x in records if isinstance(x,dict) and x.get("name")==name and x.get("event")=="schedule"],
            key=lambda x: str(x.get("created_at") or ""), reverse=True,
        )
        latest = matching[0] if matching else None
        output[name] = {
            "last_scheduled_at": (latest or {}).get("created_at"),
            "last_status": (latest or {}).get("status") or "NOT_OBSERVED",
            "last_conclusion": (latest or {}).get("conclusion") or "NOT_OBSERVED",
            "last_run_id": (latest or {}).get("id"),
            "recent_failures_in_sample": sum(x.get("conclusion") in ("failure", "timed_out") for x in matching),
            "runs_in_api_sample": len(matching),
        }
    return output


def build(binding, live, manifest, *, checked_at, run_url, workflow_runs=None):
    sections = {}
    for section, item in (binding.get("sections") or {}).items():
        sections[section] = dict(item.get("counts") or {})
    statuses = Counter(str(item.get("review_status") or "unknown") for item in live.get("items") or [])
    sampled=int(live.get("sampled") or 0)
    readable=sum(n for k,n in statuses.items() if k.startswith("page_"))
    review_health="NO_CONTENT_EXTRACTED" if sampled and not readable else (
        "PARTIAL_CONTENT" if readable<sampled else "CONTENT_READABLE"
    )
    return {
        "generated_at": checked_at,
        "snapshot_generated_at": manifest.get("generated_at"),
        "run_url": run_url,
        "status": "REVIEW_QUEUE_NOT_FACT_ACCREDITATION",
        "scope": "Independent offline claim/source binding audit and rotating live URL sample",
        "source_content_semantically_verified": False,
        "total_live_review_candidates": int(live.get("total_references") or 0),
        "live_sample_reviewed": sampled,
        "live_content_accessible": readable,
        "live_collection_health": review_health,
        "live_review_statuses": dict(statuses),
        "by_section": sections,
        "scheduled_workflows": scheduled_health(workflow_runs),
        "warning": "HTTP access and text co-occurrence do not validate a factual relationship. Consult claim-specific proof.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--binding",default="claim-source-audit.json")
    p.add_argument("--live",default="source-live-review.json")
    p.add_argument("--manifest",default="data/public/manifest.json")
    p.add_argument("--output",default="data/public/source_verification_status.json")
    p.add_argument("--run-url",default="")
    p.add_argument("--workflow-runs",default="")
    args=p.parse_args()
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    status=build(read(args.binding),read(args.live),read(args.manifest),
                 checked_at=datetime.now(timezone.utc).isoformat(),run_url=args.run_url,
                 workflow_runs=read(args.workflow_runs) if args.workflow_runs else None)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in status.items() if k!="by_section"},ensure_ascii=False))

if __name__=="__main__":
    main()
