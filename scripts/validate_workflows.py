#!/usr/bin/env python3
"""Static workflow sanity checks, including research/deployment separation."""
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
errors = []
for path in sorted(WORKFLOWS.glob("*.yml")):
    source = path.read_text(encoding="utf-8")
    try:
        obj = yaml.safe_load(source)
    except Exception as exc:
        errors.append(f"{path.name}: YAML inválido: {exc}")
        continue
    if not isinstance(obj, dict) or "jobs" not in obj:
        errors.append(f"{path.name}: sin jobs")
    if "actions/checkout@v4" in source:
        errors.append(f"{path.name}: checkout@v4 obsoleto")
    if any(s in source for s in ("data/v3", "scripts/v3", "config/v3", "assets/v3")):
        errors.append(f"{path.name}: referencia legacy")

# A deploy must never rebuild mutable research and then push an old snapshot
# over a newer main. This previously caused recurrent GitHub Pages failures.
deploy = (WORKFLOWS / "pages-deploy.yml")
if not deploy.exists():
    errors.append("pages-deploy.yml: missing")
else:
    source = deploy.read_text(encoding="utf-8")
    workflow = yaml.safe_load(source)
    steps = (workflow.get("jobs", {}).get("deploy", {}).get("steps", []))
    commands = "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, dict))
    forbidden = (
        "git push", "git commit", "git reset", "git rebase",
        "python -m engine.pipeline", "publish_research_update.py",
        "accredit_semantic_historical_sources.py",
        "revalidate_historical_sources.py",
        "attach_sase_layer_vendor_sources.py",
    )
    for pattern in forbidden:
        if pattern in commands:
            errors.append(f"pages-deploy.yml: deployment mutates research ({pattern})")
    for required in (
        "audit_public_consistency.py",
        "audit_full_visible_source_coverage.py",
        "validate_mass_historical_publication.py",
        "upload-pages-artifact@v3",
        "deploy-pages@v4",
    ):
        if required not in source:
            errors.append(f"pages-deploy.yml: missing verification/deployment ({required})")
    permissions = workflow.get("permissions", {})
    if not isinstance(permissions, dict) or permissions.get("contents") != "read":
        errors.append("pages-deploy.yml: must use contents: read")

print("workflow validation:", "PASS" if not errors else "FAIL")
for error in errors:
    print(" -", error)
sys.exit(bool(errors))
