#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Canonical Python release contract.
p = ROOT / "tests/test_release.py"
s = p.read_text(encoding="utf-8")
old = 'self.assertEqual(VERSION, "4.2.1")'
new = 'self.assertEqual(VERSION, "4.2.2")'
if new not in s:
    if old not in s:
        raise RuntimeError("v4.2.2 version-test anchor not found")
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# UI smoke identity is a release assertion too. Keep the capability test,
# but align its expected app identity with the release being installed.
u = ROOT / "tests/ui_smoke.js"
if not u.exists():
    raise RuntimeError("v4.2.2 ui_smoke.js not found")
us = u.read_text(encoding="utf-8")
for old_token in ("App v4.1.0", "App v4.2.1"):
    us = us.replace(old_token, "App v4.2.2")
for old_log in ("UI smoke v4.1.0 PASS", "UI smoke v4.2.1 PASS"):
    us = us.replace(old_log, "UI smoke v4.2.2 PASS")
if "App v4.2.2" not in us:
    raise RuntimeError("v4.2.2 UI smoke identity could not be aligned")
u.write_text(us, encoding="utf-8")

print("v4.2.2 release/UI smoke contract alignment: PASS")
