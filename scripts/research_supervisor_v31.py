#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v31.atomic_publish import DatasetSnapshot, atomic_write_json
from v31.discovery import adaptive_discover, sanitize_signal
from v31.postprocess import repair_json_tree, build_all
from v31.source_learning import LearningStore
from v31.source_registry import load_registry
from v31.validate_v31 import validate


def parse_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--profile", default="daily")
    p.add_argument("--max-runtime", type=int, default=720)
    p.add_argument("--v31-share", type=float, default=None)
    p.add_argument("--skip-legacy", action="store_true")
    known, rest = p.parse_known_args()
    return known, rest


def legacy_command(args, rest):
    legacy = ROOT / "scripts" / "research_supervisor.py"
    if not legacy.exists():
        return None
    share = args.v31_share
    if share is None:
        share = {"daily": 0.24, "weekly": 0.34, "monthly": 0.42}.get(args.profile, 0.28)
    legacy_seconds = max(60, int(args.max_runtime * (1 - share)))
    cmd = [sys.executable, str(legacy), "--profile", args.profile, "--max-runtime", str(legacy_seconds)]
    cleaned = []
    skip_next = False
    for token in rest:
        if skip_next:
            skip_next = False
            continue
        if token in {"--profile", "--max-runtime"}:
            skip_next = True
            continue
        cleaned.append(token)
    cmd += cleaned
    return cmd, legacy_seconds, share


def _load_previous_signals(path: Path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("signals", []) if isinstance(data, dict) else []
        return [x for x in rows if isinstance(x, dict)]
    except Exception:
        return []


def _signal_key(row):
    return (
        str(row.get("entity_name") or "").strip().lower(),
        str(row.get("dimension") or "").strip().lower(),
        str(row.get("url") or "").strip().lower(),
    )


def _event_key(row):
    title = str(row.get("title") or "").casefold().strip()
    title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
    title = re.sub(r"[^a-z0-9áéíóúüñçãõàâêô ]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return (
        str(row.get("entity_name") or "").strip().casefold(),
        str(row.get("dimension") or "").strip().casefold(),
        title[:190],
    )


def _merge_signals(previous, new, cap=4000):
    # First remove exact URL duplicates, then collapse syndicated copies of the same
    # event while retaining all corroborating sources and URLs.
    by_url = {}
    for row in list(previous) + list(new):
        if not row.get("url"):
            continue
        by_url[_signal_key(row)] = row

    buckets = {}
    for row in by_url.values():
        key = _event_key(row)
        current = buckets.get(key)
        if current is None:
            current = dict(row)
            current["corroborating_sources"] = list(dict.fromkeys(row.get("corroborating_sources") or [row.get("source")]))
            current["corroborating_urls"] = list(dict.fromkeys(row.get("corroborating_urls") or [row.get("url")]))
            buckets[key] = current
            continue
        sources = list(dict.fromkeys((current.get("corroborating_sources") or []) + (row.get("corroborating_sources") or [row.get("source")])))
        urls = list(dict.fromkeys((current.get("corroborating_urls") or []) + (row.get("corroborating_urls") or [row.get("url")])))
        # Keep the row with the stronger classification/strategic score as primary.
        cur_score = float(current.get("strategic_relevance_score") or current.get("classification_confidence") or 0)
        new_score = float(row.get("strategic_relevance_score") or row.get("classification_confidence") or 0)
        if new_score > cur_score:
            primary = dict(row)
            primary["corroborating_sources"] = sources
            primary["corroborating_urls"] = urls[:8]
            current = primary
            buckets[key] = current
        else:
            current["corroborating_sources"] = sources
            current["corroborating_urls"] = urls[:8]
        current["corroboration_count"] = len([x for x in sources if x])
        current["corroboration_score"] = round(min(1.0, 0.45 + 0.18 * max(0, current["corroboration_count"] - 1)), 3)

    rows = list(buckets.values())
    rows.sort(key=lambda r: str(r.get("observed_at") or r.get("published_at") or ""), reverse=True)
    return rows[:cap]


def main():
    args, rest = parse_args()
    data_root = ROOT / "data"
    data_root.mkdir(exist_ok=True)
    snapshot = DatasetSnapshot(ROOT)
    snapshot.create()
    started = time.monotonic()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "version": "3.1.5",
        "run_id": run_id,
        "profile": args.profile,
        "max_runtime": args.max_runtime,
        "snapshot": snapshot.release_id,
        "legacy": {},
        "v31": {},
    }

    try:
        if not args.skip_legacy:
            item = legacy_command(args, rest)
            if item:
                cmd, legacy_seconds, share = item
                print(f"v3.1.5 supervisor: legacy phase · {legacy_seconds}s budget · intelligence share {share:.0%}", flush=True)
                proc = subprocess.run(cmd, cwd=ROOT)
                report["legacy"] = {"returncode": proc.returncode, "budget_seconds": legacy_seconds, "status": "ok" if proc.returncode == 0 else "failed"}
                if proc.returncode != 0:
                    print(f"v3.1.5 warning · legacy phase returned {proc.returncode}; preserving valid legacy data and continuing", flush=True)
            else:
                report["legacy"] = {"skipped": True, "reason": "legacy supervisor not found"}

        registry_path = ROOT / "config" / "v31" / "source_registry.json"
        registry = load_registry(registry_path)
        seed_entities = []
        for src in registry:
            seed_entities.extend(src.get("seed_entities") or [])

        v31_dir = data_root / "v31"
        discovery_path = v31_dir / "discovery_signals.json"
        previous_raw = _load_previous_signals(discovery_path)
        previous_signals = []
        previous_removed = 0
        previous_reclassified = 0
        previous_reject_reasons = {}
        for prior in previous_raw:
            cleaned, reason = sanitize_signal(prior, profile=args.profile)
            if cleaned is None:
                previous_removed += 1
                previous_reject_reasons[reason or "unknown"] = previous_reject_reasons.get(reason or "unknown", 0) + 1
                continue
            if cleaned.get("dimension") != prior.get("dimension"):
                previous_reclassified += 1
            previous_signals.append(cleaned)
        learning = LearningStore(v31_dir / "source_learning.json")
        remaining = max(0, int(args.max_runtime - (time.monotonic() - started) - 12))
        print(
            f"v3.1.5 adaptive discovery: up to {remaining}s · {len(registry)} intelligence sources · {len(seed_entities)} seeded entities",
            flush=True,
        )

        if remaining >= 5:
            new_signals, debt, discovery_stats = adaptive_discover(
                registry, seed_entities, learning, seconds=remaining, profile=args.profile
            )
        else:
            new_signals, debt, discovery_stats = [], [{"reason": "runtime_budget_exhausted", "profile": args.profile}], {
                "attempted_tasks": 0, "completed_tasks": 0, "new_signals": 0, "debt_gaps": 1, "providers": {}
            }

        learning.save()
        for row in new_signals:
            seen_at = row.get("observed_at") or datetime.now(timezone.utc).isoformat()
            row.setdefault("first_seen_at", seen_at)
            row["last_seen_at"] = seen_at
            row["last_seen_run_id"] = run_id
            row["new_in_run_id"] = run_id
        for row in previous_signals:
            row.setdefault("first_seen_at", row.get("observed_at") or row.get("published_at"))
        merged_signals = _merge_signals(previous_signals, new_signals)
        status = "published"
        if not new_signals:
            # Never replace known-good intelligence with an empty run.
            status = "degraded" if discovery_stats.get("attempted_tasks", 0) else "budget_exhausted"
        legacy_rc = report.get("legacy", {}).get("returncode")
        if legacy_rc not in (None, 0) and status == "published":
            status = "degraded"
        atomic_write_json(discovery_path, {
            "signals": merged_signals,
            "meta": {
                "version": "3.1.5",
                "run_id": run_id,
                "run_new_signals": len(new_signals),
                "retained_previous": max(0, len(merged_signals) - len(new_signals)),
                "prior_quality_removed": previous_removed,
                "prior_reclassified": previous_reclassified,
                "prior_reject_reasons": previous_reject_reasons,
                "status": status,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "stats": discovery_stats,
            },
        })
        atomic_write_json(v31_dir / "research_debt.json", {"debt": debt, "meta": discovery_stats})

        repair = repair_json_tree(data_root)
        westcon_vendors = json.loads(
            (ROOT / "config" / "v31" / "westcon_vendor_scope.json").read_text(encoding="utf-8")
        ).get("vendors", [])
        views = build_all(data_root, registry, westcon_vendors)
        atomic_write_json(v31_dir / "entity_intelligence.json", views)
        errors = validate(ROOT)
        report["v31"] = {
            "new_signals": len(new_signals),
            "total_signals": len(merged_signals),
            "research_debt_gaps": len(debt),
            "repairs": repair,
            "discovery": discovery_stats,
            "validation_errors": errors,
        }
        if errors:
            raise RuntimeError("v3.1.5 validation failed: " + "; ".join(errors[:5]))

        report["status"] = status
        atomic_write_json(v31_dir / "last_run.json", report)
        snapshot.write_release_manifest()
        providers = discovery_stats.get("providers", {})
        provider_text = ", ".join(
            f"{name} ok {s.get('successful',0)}/{s.get('attempted',0)} raw {s.get('raw_rows',0)} accepted {s.get('accepted_rows',0)} "
            f"current {s.get('current_accepted_rows',0)} hist {s.get('historical_accepted_rows',0)} "
            f"rej[entity {s.get('relevance_rejected',0)}, geo {s.get('geo_rejected',0)}, stale {s.get('stale_rejected',0)}, semantic {s.get('semantic_rejected',0)}, own-awards {s.get('owned_awards_rejected',0)}, 3p-cert {s.get('third_party_cert_rejected',0)}, secondary-move {s.get('secondary_people_move_rejected',0)}] "
            f"reclass {s.get('semantic_reclassified',0)} latency {s.get('avg_latency_ms',0)}ms err {s.get('last_error','-')}"
            for name, s in providers.items()
        ) or "none"
        print(
            f"v3.1.5 {status} · new signals {len(new_signals)} (current {discovery_stats.get('current_signals',0)} / historical {discovery_stats.get('historical_context_signals',0)}) · total {len(merged_signals)} · "
            f"covered gaps {discovery_stats.get('covered_gaps',0)}/{discovery_stats.get('gaps',0)} · "
            f"debt gaps {len(debt)} · prior quality removed {previous_removed} · prior reclass {previous_reclassified} · repaired {repair['repairs']} · "
            f"legacy {report.get('legacy', {}).get('status', 'skipped')} · providers [{provider_text}]",
            flush=True,
        )
        # Degraded is intentionally non-fatal: legacy daily must not crash because one free discovery provider is down.
        return 0
    except Exception as exc:
        print(f"v3.1.5 rollback: {exc}", file=sys.stderr, flush=True)
        snapshot.restore()
        report["status"] = "rolled_back"
        report["error"] = repr(exc)
        try:
            atomic_write_json(ROOT / ".v31_state" / "last_failure.json", report)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
