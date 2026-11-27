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

BROKEN_SOURCE_STATUSES = frozenset({"http_404", "http_410"})


def live_claim_review(live):
    """Surface individually traceable source warnings without claiming falsity.

    HTTP failures and missing literal terms are triage signals only. In particular,
    dynamic pages and a vendor's first-party pages can omit a text string while
    still supporting the assertion in another representation or document.
    """
    sections = {}
    example_buckets = {}
    seen = set()
    unique_broken_urls = set()
    for row in live.get("items") or []:
        if not isinstance(row, dict):
            continue
        section = str(row.get("section") or "unknown")
        status = str(row.get("review_status") or "unknown")
        counts = sections.setdefault(section, {
            "reviewed": 0, "content_readable": 0, "value_absent": 0,
            "value_only": 0, "joint_mention_unverified": 0,
            "unreadable_or_blocked": 0, "broken_url_references": 0,
        })
        counts["reviewed"] += 1
        if status.startswith("page_"):
            counts["content_readable"] += 1
            category = {
                "page_does_not_mention_value": "value_absent",
                "page_mentions_value_only": "value_only",
                "page_mentions_entity_and_value_needs_semantic_review": "joint_mention_unverified",
            }.get(status)
            if category:
                counts[category] += 1
        else:
            counts["unreadable_or_blocked"] += 1
        if status in BROKEN_SOURCE_STATUSES:
            counts["broken_url_references"] += 1
            unique_broken_urls.add(str(row.get("url") or ""))
        # Illustrations stay small, section-diverse and attributable to an
        # exact published claim. The complete inspection remains in the Actions
        # artifact; these examples must never be described as an exhaustive list.
        if status in BROKEN_SOURCE_STATUSES or status == "page_does_not_mention_value":
            priority = status in BROKEN_SOURCE_STATUSES
            key = (section, priority, str(row.get("url") or ""))
            bucket = example_buckets.setdefault((section, priority), [])
            if key not in seen and len(bucket) < 2:
                seen.add(key)
                bucket.append({
                    key: str(row.get(key) or "")[:300]
                    for key in ("section", "entity", "field", "value", "url", "review_status")
                })
    # Prioritise broken links, with a small fair sample from every section.
    selected = []
    for priority in (True, False):
        for section in sorted(sections):
            selected.extend(example_buckets.get((section, priority), []))
    return {
        "by_section": sections,
        "broken_unique_urls": len(unique_broken_urls),
        "review_examples": selected[:28],
        "examples_are_exhaustive": False,
        "semantic_accreditation_from_live_review": False,
    }


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
    review_health="NO_CONTENT_EXTRACTED" if not readable else (
        "PARTIAL_CONTENT" if readable<sampled else "CONTENT_READABLE"
    )
    review = live_claim_review(live)
    return {
        "generated_at": checked_at,
        "snapshot_generated_at": manifest.get("generated_at"),
        "run_url": run_url,
        "status": "REVIEW_QUEUE_NOT_FACT_ACCREDITATION",
        "scope": "Independent claim/source binding audit and live source review",
        "live_unique_urls": live.get("unique_urls"),
        "source_content_semantically_verified": False,
        "total_live_review_candidates": int(live.get("total_references") or 0),
        "live_sample_reviewed": sampled,
        "live_sample_hosts": int(live.get("unique_source_hosts_in_sample") or 0),
        "live_sampling_policy": str(live.get("sampling_policy") or "legacy-contiguous"),
        "live_content_accessible": readable,
        "live_collection_health": review_health,
        "live_review_statuses": dict(statuses),
        "live_claim_review": review,
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
