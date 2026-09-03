#!/usr/bin/env python3
from pathlib import Path

path = Path('tests/test_release.py')
text = path.read_text(encoding='utf-8')
old = 'self.assertEqual(VERSION, "4.2.0")'
new = 'self.assertEqual(VERSION, "4.2.1")'
if new in text:
    print('v4.2.1 release-test contract already aligned')
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')
    print('v4.2.1 release-test contract alignment: PASS')
else:
    raise SystemExit('Unexpected test_release.py VERSION contract; refusing to patch')
