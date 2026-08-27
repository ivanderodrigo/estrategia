#!/usr/bin/env python3
"""Deterministic checkpoint/resume regression test; never accesses the network."""
from __future__ import annotations
import importlib.util
import pathlib
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("westcon_research_resilience", ROOT / "scripts/research.py")
research = importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader; SPEC.loader.exec_module(research)

queries = [
    {"query":"alpha Spain distributor","kind":"vendor","vendor":"Cisco","country":"ES","intent":"channel","priority":100},
    {"query":"beta Portugal integrator","kind":"vendor","vendor":"F5","country":"PT","intent":"ecosystem","priority":99}
]

def fake_search(qrow):
    return [{"title":qrow["query"],"snippet":"public result Spain Portugal","url":f"https://example.com/{research.sha(qrow['query'])}","published":"2026-08-27","engine":"test"}]

with tempfile.TemporaryDirectory() as tmp:
    research.QUEUE_OUT = pathlib.Path(tmp) / "queue.json"
    research.LEARNING_OUT = pathlib.Path(tmp) / "learning.json"
    research.search_google_news = research.search_gdelt = research.search_arquivo = fake_search
    research.BUDGETS.update({"news_queries_max":2,"gdelt_queries_max":2,"arquivo_queries_max":1,"batch_size":2,"finalize_reserve_seconds":0,"discovery_stage_seconds":30})
    research.MAX_RUNTIME_SECONDS=90;research.DEADLINE=time.monotonic()+90
    research.STOP_REQUESTED=True
    rows,stats=research.run_discovery_batches(queries)
    assert stats["partialRun"] and stats["pendingTasks"]>0 and not rows
    research.STOP_REQUESTED=False;research.DEADLINE=time.monotonic()+90
    rows,stats=research.run_discovery_batches(queries)
    assert not stats["partialRun"] and stats["pendingTasks"]==0 and len(rows)>=4
    queue=research.load_json_state(research.QUEUE_OUT,{})
    assert queue.get("complete") is True and queue.get("partialEvidence")==[]

print("OK · checkpoint/resume · partial publication · deterministic recovery")
