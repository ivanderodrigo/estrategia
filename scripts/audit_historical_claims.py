"""Read-only comparison of historical Westcon claims and sources."""
import csv, json, subprocess
from collections import Counter
from pathlib import Path
from engine.storage import read_json
from engine.model import canonical

SECTIONS=("manufacturers","distributors","integrators","clients_public","clients_private","trends","architectures")
REVS=("69505c660","18bc84f35","c6f82503d","0b22de853","17c751970","5cf8fe7d3","9344ed99f","f56559492","198b689f3","ec0dfea36","c20f8dd4af","589cf96deb","7f5c019c26","7f955f4906","d3401b7a08","0059d7b225","6c8141c9d4")
def read(rev,path):
    p=subprocess.run(("git","show",rev+":"+path),capture_output=True)
    if p.returncode:return None
    try:return json.loads(p.stdout)
    except (UnicodeDecodeError,ValueError):return None
def vals(x):
    x=x.get("value")
    return x if isinstance(x,list) else ([] if x is None or x=="" else [x])
def ident(s,r):
    return canonical(r.get("name") or "")+(("|"+canonical(((r.get("fields") or {}).get("notice_id") or {}).get("value"))) if s=="clients_public" else "")
def rows(s,data):
    for r in data:
        for f,v in (r.get("fields") or {}).items():
            if not isinstance(v,dict):continue
            for x in vals(v):
                yield (s,ident(s,r),f,json.dumps(x,ensure_ascii=False,sort_keys=True)),r,v,x
def main():
    out=Path("historical_audit");out.mkdir(exist_ok=True)
    cur=read_json("data/current/intelligence.json")
    current=set()
    for s in SECTIONS:
        current.update(k for k,_,_,_ in rows(s,cur.get(s) or []))
    older={};snapshots=[]
    for rev in REVS:
        for section in SECTIONS:
            d=read(rev,"data/public/sections/"+section+".json")
            if not isinstance(d,dict):continue
            snapshots.append({"rev":rev,"section":section,"rows":len(d.get("rows") or [])})
            ev=d.get("evidence") or {}
            for key,row,field,value in rows(section,d.get("rows") or []):
                record=older.setdefault(key,{"entity":row.get("name"),"first":rev,"last":rev,"sources":set(),"documents":set(),"confidence":[]})
                record["last"]=rev
                record["confidence"].append(field.get("confidence") or 0)
                ids=list(field.get("evidence_ids") or [])
                for item in field.get("items") or []:
                    if item.get("value")==value:ids.extend(item.get("evidence_ids") or [])
                for eid in ids:
                    source=ev.get(eid) or {}
                    if source.get("url"):record["sources"].add(str(source["url"]))
                    if source.get("document") or source.get("document_id"):record["documents"].add(str(source.get("document_id") or source.get("document")))
    count=Counter();candidates=[]
    for key,v in older.items():
        cls="present" if key in current else "historical-only"
        typ=("public-source" if v["sources"] else ("document" if v["documents"] else "unproven"))
        count[cls]+=1;count[cls+"_"+typ]+=1
        if cls=="historical-only":
            candidates.append([*key,v["first"],v["last"],max(v["confidence"]),typ,";".join(sorted(v["sources"])),";".join(sorted(v["documents"]))])
    with (out/"historical_candidates.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(("section","entity","field","value_json","first","last","max_legacy_confidence","source_type","urls","documents"));w.writerows(sorted(candidates))
    summary={"snapshots":snapshots,"revisions":REVS,"historical_claims":len(older),"current_claims":len(current),"counts":dict(count),
             "note":"READ ONLY. Historical URLs and confidence are not verified current claims. Name-key ambiguities require review."}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"historical":len(older),"current":len(current),"counts":dict(count)},ensure_ascii=False))
if __name__=="__main__":main()
