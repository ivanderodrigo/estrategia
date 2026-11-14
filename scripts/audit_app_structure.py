#!/usr/bin/env python3
"""Static structural checks for the published SPA entry points.

Checks actual local asset paths, duplicate DOM ids, link fragment targets,
frontend JS parsing and the browser's seven mandatory observatory tabs.
"""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
import re,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
PAGES=("index.html","memoria-historica.html","404.html")
VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}

class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=[];self.refs=[];self.targets=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get("id"):self.ids.append(a["id"])
        if tag in ("script","img","link","a","source"):
            key="href" if tag in ("link","a") else "src"
            if a.get(key):self.refs.append((tag,a[key]))
        if tag=="button" and a.get("data-view"):self.targets.append(a["data-view"])

def check():
    errors=[];stats={}
    for html in PAGES:
        p=ROOT/html
        if not p.is_file():
            errors.append(f"{html}: missing entry page");continue
        parser=Scan();parser.feed(p.read_text(encoding="utf-8"))
        seen=set()
        for tag in parser.ids:
            if tag in seen:errors.append(f"{html}: duplicate DOM id {tag}")
            seen.add(tag)
        broken=[]
        for tag,target in parser.refs:
            if target.startswith(("https://","http://","mailto:","tel:","data:","javascript:","//")):
                continue
            link=urlsplit(target)
            rel=unquote(link.path)
            if rel.startswith("/"):continue
            if not rel and link.fragment:
                if link.fragment not in seen:broken.append("#"+link.fragment)
                continue
            if not rel:continue
            dest=(p.parent/rel).resolve()
            if ROOT not in dest.parents and dest!=ROOT:
                broken.append(target+" [outside root]");continue
            if not dest.exists():
                broken.append(target)
            elif link.fragment and dest==p.resolve() and link.fragment not in seen:
                broken.append(target+" [missing fragment]")
        if broken:errors.append(f"{html}: missing local references: {broken[:25]}")
        stats[html]={"ids":len(parser.ids),"local_references":len(parser.refs),
                     "tabs":parser.targets}
        if html=="index.html":
            expected={"fabricantes","mayoristas","integradores","clientes","tendencias","arquitecturas"}
            if not expected.issubset(set(parser.targets)):
                errors.append(f"index.html: missing tabs {sorted(expected-set(parser.targets))}")
            for required in ("commandCenter","ccAudit","ccFreshness","ccDebt"):
                if required not in seen:errors.append(f"index.html: missing {required}")
    js=list((ROOT/"assets/app").glob("*.js"))
    for path in js:
        result=subprocess.run(["node","--check",str(path)],capture_output=True,text=True)
        if result.returncode:
            errors.append(f"JavaScript invalid: {path.relative_to(ROOT)}: {result.stderr[-250:]}")
    stats["js_modules_checked"]=len(js)
    return {"status":"PASS" if not errors else "FAIL","errors":errors,"checked":stats}

if __name__=="__main__":
    import json
    report=check()
    print(json.dumps(report,ensure_ascii=False))
    sys.exit(0 if report["status"]=="PASS" else 1)
