from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

REL = {
    "distribution_agreement":"DISTRIBUTED_BY",
    "partnership":"PARTNERS_WITH",
    "customer_reference":"CUSTOMER_RELATION",
    "certification":"CERTIFIED_CAPABILITY",
    "award":"AWARDED",
    "ma_acquisition":"ACQUIRED_OR_MERGED",
    "investment":"INVESTED_IN",
    "product_release":"RELEASED",
    "service_launch":"LAUNCHED_SERVICE",
    "managed_service":"MANAGED_SERVICE",
    "market_expansion":"EXPANDED_TO",
    "analyst_positioning":"ANALYST_POSITION",
    "security_incident":"SECURITY_INCIDENT",
    "operational_incident":"OPERATIONAL_INCIDENT",
    "regulatory_change":"AFFECTED_BY_REGULATION",
    "known_exploited_vulnerability":"AFFECTED_BY_KEV",
    "security_vulnerability":"AFFECTED_BY_VULNERABILITY",
}


def _id(prefix: str, value: str) -> str:
    return prefix + "_" + hashlib.sha1(value.casefold().encode("utf-8")).hexdigest()[:12]


def build_graph(events: Iterable[Mapping[str,Any]]) -> Dict[str,Any]:
    nodes: Dict[str,Dict[str,Any]]={}
    edges=[];seen_edges=set()

    def node(label:str,kind:str="external_entity") -> str:
        nid=_id("ent",label)
        nodes.setdefault(nid,{"id":nid,"label":label,"kind":kind,"events":0,"max_materiality":0.0})
        return nid

    def edge(src:str,rel:str,dst:str,e:Mapping[str,Any]):
        key=(src,rel,dst,str(e.get("event_id")))
        if key in seen_edges:return
        seen_edges.add(key)
        edges.append({
            "from":src,"to":dst,"from_label":nodes[src]["label"],"to_label":nodes[dst]["label"],
            "from_kind":nodes[src]["kind"],"to_kind":nodes[dst]["kind"],"relation":rel,"event_id":e.get("event_id"),
            "title":e.get("title"),"confidence":e.get("confidence"),"materiality":e.get("materiality"),"scope":e.get("market_scope"),
            "date":e.get("published_at"),"sources":e.get("corroborating_sources") or [e.get("source")]
        })

    for e in events:
        entity=str(e.get("entity_name") or "").strip()
        if not entity:continue
        eid=node(entity,str(e.get("entity_type") or "entity"));nodes[eid]["events"]+=1
        nodes[eid]["max_materiality"]=max(float(nodes[eid].get("max_materiality") or 0),float(e.get("materiality") or 0))
        t=str(e.get("event_type") or "")

        if t in {"procurement_award","procurement_notice"}:
            buyer=str(e.get("buyer_name") or "").strip();winner=str(e.get("winner_name") or "").strip()
            if t=="procurement_award" and buyer and winner:
                bid=node(buyer,"buyer");wid=node(winner,"supplier")
                edge(bid,"AWARDED_CONTRACT_TO",wid,e)
                continue
            if t=="procurement_notice" and buyer:
                bid=node(buyer,"buyer")
                techs=list(e.get("technology_domains") or []) or ["Technology procurement"]
                for tech in techs[:3]:
                    tid=node(str(tech),"technology")
                    edge(bid,"PUBLISHED_TECH_TENDER",tid,e)
                continue

        obj=str(e.get("object_entity") or "").strip();rel=REL.get(t)
        if obj and rel:
            oid=node(obj,str(e.get("object_entity_type") or "external_entity"));edge(eid,rel,oid,e)
        elif t in {"certification","product_release","service_launch","managed_service","analyst_positioning","capability_expansion"}:
            rel2={"certification":"CERTIFIED_CAPABILITY","product_release":"RELEASED_IN_DOMAIN","service_launch":"LAUNCHED_SERVICE_IN_DOMAIN","managed_service":"MANAGED_SERVICE_IN_DOMAIN","analyst_positioning":"ANALYST_POSITION_IN","capability_expansion":"EXPANDED_CAPABILITY_IN"}.get(t)
            for tech in list(e.get("technology_domains") or [])[:3]:
                tid=node(str(tech),"technology");edge(eid,rel2,tid,e)

    degree=defaultdict(int)
    for ed in edges:degree[ed["from"]]+=1;degree[ed["to"]]+=1
    for nid,n in nodes.items():n["degree"]=degree[nid]
    return {"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"nodes":len(nodes),"edges":len(edges)},"nodes":list(nodes.values()),"edges":edges}
