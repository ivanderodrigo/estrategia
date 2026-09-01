#!/usr/bin/env python3
"""Fast repository security checks with no external service dependency."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".js", ".yml", ".yaml", ".json", ".md", ".html", ".css", ".txt"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|client[_-]?secret|password|passwd)\s*[:=]\s*['\"][^'\"]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
)
DANGEROUS_PATTERNS = (
    (re.compile(r"\bshell\s*=\s*True\b"), "subprocess shell execution enabled"),
    (re.compile(r"\bpickle\.loads?\("), "unsafe pickle load"),
    (re.compile(r"\byaml\.load\("), "unsafe yaml.load"),
    (re.compile(r"\beval\("), "eval"),
)


def repository_files() -> list[Path]:
    ignored_parts = {
        ".git", "__pycache__", ".runtime", ".cache", "_site",
        ".westcon-update-rollback", ".local-backups",
    }
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not ignored_parts.intersection(path.relative_to(ROOT).parts)
    ]


def main() -> int:
    errors: list[str] = []
    for path in repository_files():
        if not path.is_file() or (path.suffix not in TEXT_SUFFIXES and path.name not in {"VERSION", ".gitignore", ".gitattributes"}):
            continue
        if path.stat().st_size > 5_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        relative = path.relative_to(ROOT)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible credential in {relative}")
        if path.suffix == ".py":
            for pattern, label in DANGEROUS_PATTERNS:
                if pattern.search(text):
                    errors.append(f"{label} in {relative}")

    web_runner = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
    if "validate_public_url(response.url)" not in web_runner:
        errors.append("redirect destinations are not revalidated")
    if "MAX_RESPONSE_BYTES" not in web_runner:
        errors.append("network response size is not bounded")
    public_workflow = (ROOT / ".github/workflows/pages-deploy.yml").read_text(encoding="utf-8")
    if "cp data/current" in public_workflow:
        errors.append("internal intelligence would be published to Pages")

    print("security audit:", "PASS" if not errors else "FAIL")
    for error in errors:
        print(" -", error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
