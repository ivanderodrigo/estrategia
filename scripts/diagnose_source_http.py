#!/usr/bin/env python3
"""Bounded diagnostic for uniform HTTP 202 responses in source review.

Does not verify or accredit claims. Never records URL query paths, cookies,
tokens or response bodies. Verifies public targets before any network fetch.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from engine.research.security import validate_public_url

REPORT=Path("source-live-review.json")
OUTPUT=Path("source-http-diagnostics.json")
def main():
    data=json.loads(REPORT.read_text(encoding="utf-8"))
    selected=[]
    seen=set()
    for item in data.get("items") or []:
        url=str(item.get("url") or "")
        host=(urlparse(url).hostname or "").lower()
        if not host or host in seen:
            continue
        selected.append(url)
        seen.add(host)
        if len(selected)==3:
            break
    result={"checked_at":datetime.now(timezone.utc).isoformat(),
            "purpose":"HTTP transport diagnostics; never semantic accreditation",
            "probes":[]}
    headers_sets=[
        ("standard",{"User-Agent":"Westcon-Research-Auditor/1.0","Accept":"text/html,*/*"}),
        ("browser_accept",{"User-Agent":"Mozilla/5.0 (compatible; WestconEvidenceAudit/1.0)",
                           "Accept":"text/html,application/xhtml+xml;q=0.9,*/*;q=0.7"}),
    ]
    for url in selected:
        host=(urlparse(url).hostname or "").lower()
        for mode,headers in headers_sets:
            entry={"host":host,"mode":mode}
            try:
                safe=validate_public_url(url)
                with requests.get(safe,headers=headers,timeout=(3,7),allow_redirects=False,stream=True) as response:
                    chunks=[]
                    size=0
                    for chunk in response.iter_content(chunk_size=8192):
                        size+=len(chunk)
                        chunks.append(chunk)
                        if size>=16384:
                            break
                    entry.update(status=response.status_code,
                        content_type=str(response.headers.get("Content-Type",""))[:100],
                        declared_length=str(response.headers.get("Content-Length",""))[:30],
                        sampled_bytes=size,
                        likely_html=bool(b"<html" in b"".join(chunks).lower()))
            except Exception as exc:
                entry["error_type"]=type(exc).__name__
            result["probes"].append(entry)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
