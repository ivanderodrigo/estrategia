#!/usr/bin/env python3
"""Recover URL-bearing claims from additional Git snapshots, without accreditation.

The existing historical sidecars cover a small fixed collection of revisions.
This independent archive survey samples the full Git history of each section,
deduplicating URL / claim tuples and retaining the original Git revision.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("manufacturers", "distributors", "integrators", "clients_public",
            "clients_private", "trends", "architectures")
OUTPUT = ROOT / "data/public/historical/current/git_archive_additions.json"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)


def choose_revisions(section, limit):
    path = "data/public/sections/" + section + ".json"
    result = git("log", "--all", "--format=%H", "--", path)
    if result.returncode:
        return []
    commits = list(dict.fromkeys(result.stdout.decode("utf-8", "replace").splitlines()))
    if len(commits) <= limit:
        return commits
    positions = {round(i * (len(commits) - 1) / (limit - 1))
                 for i in range(limit)}
    return [commits[i] for i in sorted(positions)]


def archive_rows(rev, section):
    proc = git("show", rev + ":data/public/sections/" + section + ".json")
    if proc.returncode or not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout)
    except (ValueError, UnicodeDecodeError):
        return None


def source_urls(evidence, registry):
    ids = evidence.get("evidence_ids") or []
    direct = evidence.get("evidence") or []
    candidates = [registry.get(str(i), {}) for i in ids] + direct
    if evidence.get("url"):
        candidates.append(evidence)
    for item in candidates:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc and len(url) <= 2000:
            yield url


def atom_values(field):
    value = field.get("value")
    if isinstance(value, list):
        return [str(x) for x in value if isinstance(x, (str, int, float))
                and str(x).strip()]
    if isinstance(value, (str, int, float)) and str(value).strip():
        return [str(value)]
    return []


def recover(max_snapshots=32, max_pairs=30000):
    discovered = {}
    samples = {}
    snapshots = Counter()
    attempted = Counter()
    for section in SECTIONS:
        for rev in choose_revisions(section, max_snapshots):
            attempted[section] += 1
            payload = archive_rows(rev, section)
            if not isinstance(payload, dict):
                continue
            snapshots[section] += 1
            registry = payload.get("evidence") or {}
            for row in payload.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                entity = str(row.get("name") or "").strip()
                if not entity:
                    continue
                # Entity-level evidence is an identity lead only.
                for url in source_urls(row, registry):
                    key = (section, entity, "__identity__", entity, url)
                    if key not in discovered:
                        discovered[key] = rev[:12]
                for field_name, field in (row.get("fields") or {}).items():
                    if not isinstance(field, dict):
                        continue
                    shared = set(source_urls(field, registry))
                    for value in atom_values(field):
                        # Legacy shared URLs are leads, NOT proof for list members.
                        for url in shared:
                            key = (section, entity, field_name, value, url)
                            if key not in discovered:
                                discovered[key] = rev[:12]
                    for item in field.get("items") or []:
                        if not isinstance(item, dict):
                            continue
                        value = item.get("value")
                        if not isinstance(value, (str, int, float)) or not str(value).strip():
                            continue
                        for url in source_urls(item, registry):
                            key = (section, entity, field_name, str(value), url)
                            if key not in discovered:
                                discovered[key] = rev[:12]
            if len(discovered) >= max_pairs:
                break
        if len(discovered) >= max_pairs:
            break

    # Retain exact claims, with provenance, as NON-accredited research leads.
    records = [{"section": s, "entity": e, "field": f, "value": v,
                "url": url, "revision": rev, "inventory_origin": "git-archive-recovered"}
               for (s, e, f, v, url), rev in sorted(discovered.items())]
    existing = set()
    for section in SECTIONS:
        path = ROOT / f"data/public/historical/current/{section}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for entity, fields in (data.get("entities") or {}).items():
            for field, claims in fields.items():
                for claim in claims:
                    if not isinstance(claim.get("value"), str):
                        continue
                    for url in claim.get("urls") or []:
                        existing.add((section, entity, field, claim["value"], url))
    # The new output reports genuinely unseen tuples separately.
    additions = [r for r in records if
                 (r["section"], r["entity"].lower(), r["field"],
                  r["value"], r["url"]) not in existing]
    by_section = Counter(r["section"] for r in additions)
    output = {
        "status": "HISTORICAL_GIT_LEADS_NOT_ACCREDITED",
        "policy": "Archived Git URL tuples are investigative leads, never direct accreditation.",
        "sampled_snapshots": dict(snapshots),
        "attempted_snapshots": dict(attempted),
        "all_archived_pairs": len(records),
        "additional_claim_url_pairs": len(additions),
        "additional_unique_urls": len({r["url"] for r in additions}),
        "by_section": dict(by_section),
        "claims": additions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    print(json.dumps({k:v for k,v in output.items() if k != "claims"}, ensure_ascii=False))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=int, default=32)
    parser.add_argument("--max-pairs", type=int, default=30000)
    args = parser.parse_args()
    recover(max(2, args.snapshots), max(100, args.max_pairs))


if __name__ == "__main__":
    main()
