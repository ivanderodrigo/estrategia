"""Read-only comparison of historical Westcon claims and sources."""
import csv, json, subprocess
from collections import Counter, defaultdict
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
    # Lightweight public exploration index. Claims are HISTORICAL CANDIDATES,
    # not validated facts and never written into canonical intelligence.
    public_index=[]
    for section,entity,field,value_json,first,last,confidence,typ,urls,documents in sorted(candidates):
        public_index.append({
            "section":section,"entity":entity,"field":field,
            "value":value_json[:500],"first_revision":first,"last_revision":last,
            "legacy_confidence":confidence,"source_type":typ,
            "urls":urls.split(";")[:5] if urls else [],
            "documents":documents.split(";")[:5] if documents else [],
            "status":"HISTORICAL_CANDIDATE_NOT_REVALIDATED"
        })
    (out/"candidate_index.json").write_text(
        json.dumps({"version":1,"status":"read-only-historical",
          "source_revision_count":len(REVS),"candidate_count":len(public_index),
          "candidates":public_index},ensure_ascii=False,separators=(",",":")),
        encoding="utf-8")
    # Cross-reference every CURRENT research task against the evidence-bearing
    # historical assertions. A candidate match never resolves a task by itself.
    gaps_doc=read_json("data/current/research_gaps.json", {})
    open_gaps=(gaps_doc.get("gaps") or []) if isinstance(gaps_doc,dict) else []
    by_field=defaultdict(list)
    for key,record in older.items():
        section,entity_key,field,value_json=key
        # Public procurement buyer names are not notice identifiers; never
        # claim exact identity for buyer-only matches.
        lookup_entity=entity_key.split("|",1)[0] if section=="clients_public" else entity_key
        by_field[(section,lookup_entity,field)].append((key,record))
    matched_gaps=[]
    match_counts=Counter()
    by_section=Counter()
    for gap in open_gaps:
        if not isinstance(gap,dict): continue
        section=str(gap.get("section") or "")
        entity=str(gap.get("entity") or "")
        field=str(gap.get("field") or "")
        options=by_field.get((section,canonical(entity),field),[])
        if not options:continue
        targets=gap.get("target_values") or []
        exact_values={json.dumps(v,ensure_ascii=False,sort_keys=True) for v in targets}
        exact=[(key,rec) for key,rec in options if key[3] in exact_values] if targets else []
        selected=exact or options
        source_links=sorted({url for _,rec in selected for url in rec["sources"] if url.startswith(("http://","https://"))})
        confidence="exact-value-history" if exact else ("field-only-history" if not targets else "other-historical-value")
        identity_scope="buyer-name-only-not-notice" if section=="clients_public" else "canonical-name"
        match_counts[confidence]+=1
        if source_links:match_counts["gaps_with_historical_urls"]+=1
        by_section[section]+=1
        sample=[{"value":key[3][:320],"first_revision":rec["first"],"last_revision":rec["last"],
                 "source_urls":sorted(rec["sources"])[:3], "documents":sorted(rec["documents"])[:3],
                 "present_in_current":key in current} for key,rec in selected[:6]]
        matched_gaps.append({"gap_id":str(gap.get("id") or ""),
            "section":section,"entity":entity,"field":field,
            "gap_kind":str(gap.get("gap_kind") or ""),
            "research_state":str(gap.get("research_state") or ""),
            "priority_tier":str(gap.get("priority_tier") or ""),
            "match_level":confidence,"identity_scope":identity_scope,
            "historical_assertions":len(selected),"urls_found":len(source_links),
            "source_urls":source_links[:5],"historical_samples":sample,
            "status":"HISTORICAL_RESEARCH_LEAD_NOT_VERIFIED"})
    publication=read_json("data/current/last_run.json", {})
    gap_summary={"version":1,"dataset_published_at":publication.get("generated_at"),
        "total_current_research_tasks":len(open_gaps),
        "tasks_with_historical_antecedents":len(matched_gaps),
        "tasks_without_exact_name_field_history":len(open_gaps)-len(matched_gaps),
        "by_match_level":dict(match_counts),
        "by_section":dict(by_section),
        "notice":"Historical references are research leads only. No gap is closed; no historical URL is taken as a currently valid source."}
    (out/"gap_summary.json").write_text(json.dumps(gap_summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"gap_matches.json").write_text(json.dumps({
      "version":1,"status":"read-only-historical","summary":gap_summary,
      "matches":matched_gaps},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    with (out/"gap_matches.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        writer=csv.writer(fh);writer.writerow(("gap_id","section","entity","field","gap_kind","research_state",
            "priority_tier","match_level","identity_scope","historical_assertions","urls_found","source_urls"))
        for item in matched_gaps:
            writer.writerow([item.get(k) if k!="source_urls" else ";".join(item["source_urls"]) for k in
                ("gap_id","section","entity","field","gap_kind","research_state",
                 "priority_tier","match_level","identity_scope","historical_assertions","urls_found","source_urls")])
    summary={"snapshots":snapshots,"revisions":REVS,"historical_claims":len(older),"current_claims":len(current),"counts":dict(count),"gap_intersection":gap_summary,
             "note":"READ ONLY. Historical URLs and confidence are not verified current claims. Name-key ambiguities require review."}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"historical":len(older),"current":len(current),"counts":dict(count)},ensure_ascii=False))
if __name__=="__main__":main()
