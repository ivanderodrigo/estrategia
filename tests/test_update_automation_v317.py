from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('publisher',ROOT/'scripts/publish_research_update.py')
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)

version,tag=publisher.current_version()
assert (version,tag)==('3.17.0','v317')
paths=publisher.generated_paths()
assert 'data/v317' in paths and 'data/v312' not in paths
publisher.validate()
print('AUTOMATION v3.17 · dynamic publisher + current validator · PASS')
