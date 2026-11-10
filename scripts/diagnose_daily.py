#!/usr/bin/env python3
"""Reproducible Daily preflight diagnostic, independent of the research/publish path."""
from __future__ import annotations
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/current/daily_preflight_health.json"

CHECKS = [
    ("compile", [sys.executable, "-m", "compileall", "-q", "engine", "scripts", "tests"]),
    ("unit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]),
    ("workflow_validation", [sys.executable, "scripts/validate_workflows.py"]),
    ("security_audit", [sys.executable, "scripts/security_audit.py"]),
    ("data_validation", [sys.executable, "scripts/validate.py"]),
    ("release_audit_v410", [sys.executable, "scripts/audit_release_v410.py"]),
    ("release_audit_v421", [sys.executable, "-m", "scripts.audit_v421"]),
    ("release_audit_v422", [sys.executable, "-m", "scripts.audit_v422"]),
    ("release_audit_v430", [sys.executable, "-m", "scripts.audit_v430"]),
    ("node_syntax", ["node", "--check", "assets/app/intelligence.js"]),
    ("node_command_center", ["node", "--check", "assets/app/command-center.js"]),
    ("ui_smoke", ["node", "tests/ui_smoke.js"]),
    ("filter_builder", ["node", "tests/filter_builder_v410.js"]),
]

def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    results = []
    for name, args in CHECKS:
        begin = time.monotonic()
        try:
            completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                       timeout=180, errors="replace", check=False)
            combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
            status = "passed" if completed.returncode == 0 else "failed"
            code = completed.returncode
        except subprocess.TimeoutExpired:
            combined, status, code = "Timed out after 180 seconds", "timeout", 124
        except Exception as exc:
            combined, status, code = f"{type(exc).__name__}: {exc}", "exception", 1
        item = {
            "name": name, "status": status, "returncode": code,
            "elapsed_seconds": round(time.monotonic()-begin, 2),
            "output_tail": combined[-7000:] if status != "passed" else combined[-450:],
        }
        results.append(item)
        print(f"daily diagnostic: {name}: {status}", flush=True)
        # Stop at the first failure; mirrors canonical preflight's fail-fast behavior.
        if status != "passed":
            break
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started,
        "conclusion": "passed" if len(results) == len(CHECKS) and all(x["status"] == "passed" for x in results) else "failed",
        "failed_step": next((x["name"] for x in results if x["status"] != "passed"), None),
        "steps": results,
        "scope": "Preflight only. Does not certify successful web research or publication.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["conclusion"] == "passed" else 1

if __name__ == "__main__":
    raise SystemExit(main())
