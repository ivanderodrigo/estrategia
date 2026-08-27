from __future__ import annotations
from collections import defaultdict
from .common import iso_now,clamp,f

ARCHS=[
 {"id":"sase-zero-trust","title":"SASE / SSE + Zero Trust","subtitle":"Acceso seguro desde usuario y sede hasta aplicaciones y cloud.","layers":[
   {"name":"Usuarios y sedes","domains":["Identity","Networking"]},{"name":"Acceso y conectividad","domains":["Networking","SASE/SSE"]},{"name":"Controles de seguridad","domains":["SASE/SSE","Cybersecurity","Identity"]},{"name":"Aplicaciones y cloud","domains":["Cloud","Data Center"]},{"name":"Operación transversal","domains":["Observability","Automation"]}],
  "outcomes":["Consolidar controles de acceso","Reducir complejidad de red y seguridad","Aumentar servicios recurrentes"],"motions":["Assessment Zero Trust","SASE/SSE workshop","Managed security attach"]},
 {"id":"ai-secops","title":"AI-ready Security Operations","subtitle":"Arquitectura de SecOps preparada para automatización e IA.","layers":[
   {"name":"Fuentes de telemetría","domains":["Cybersecurity","Networking","Cloud"]},{"name":"Observabilidad y datos","domains":["Observability","Data Center"]},{"name":"Detección y respuesta","domains":["Cybersecurity","AI"]},{"name":"Automatización","domains":["Automation","AI"]}],
  "outcomes":["Reducir tiempo de detección y respuesta","Escalar SOC sin crecer linealmente en personas","Crear servicios gestionados"],"motions":["SOC modernization","XDR/SIEM rationalization","Automation services"]},
 {"id":"hybrid-cloud","title":"Hybrid Cloud + Data Center","subtitle":"Cloud híbrida segura, observable y automatizada.","layers":[
   {"name":"Workloads","domains":["Cloud","Data Center"]},{"name":"Conectividad","domains":["Networking"]},{"name":"Seguridad","domains":["Cybersecurity","Identity"]},{"name":"Observabilidad","domains":["Observability"]},{"name":"Automatización y operación","domains":["Automation","AI"]}],
  "outcomes":["Acelerar modernización","Optimizar operación híbrida","Aumentar attach de servicios"],"motions":["Hybrid cloud assessment","DC modernization","Observability attach"]},
 {"id":"naas","title":"Secure Networking / NaaS","subtitle":"Red empresarial consumible, automatizada y con seguridad integrada.","layers":[
   {"name":"Campus / Branch / Edge","domains":["Networking"]},{"name":"WAN y acceso","domains":["Networking","SASE/SSE"]},{"name":"Policy y seguridad","domains":["Cybersecurity","Identity"]},{"name":"Control y automatización","domains":["Automation","Observability"]}],
  "outcomes":["Simplificar lifecycle","Crear recurrencia","Mejorar experiencia operativa"],"motions":["NaaS discovery","Managed network","Lifecycle services"]},
 {"id":"identity-security","title":"Identity-first Security","subtitle":"Identidad como control transversal de acceso y protección.","layers":[
   {"name":"Identidades","domains":["Identity"]},{"name":"Acceso","domains":["SASE/SSE","Cybersecurity"]},{"name":"Aplicaciones","domains":["Cloud","Data Center"]},{"name":"Detección","domains":["Observability","Cybersecurity"]}],
  "outcomes":["Reducir superficie de ataque","Unificar acceso","Crear plays de Zero Trust"],"motions":["Identity posture assessment","ZTNA attach","PAM/MFA services"]}
]


def build_architectures(portfolio_doc,westcon_vendors,profiles=None):
    vendors=portfolio_doc.get("vendors",[]) or [];profiles=profiles or [];by_domain=defaultdict(list)
    for v in vendors:
        name=v.get("vendor")
        if not name:continue
        for d in v.get("top_technologies") or []:by_domain[d].append({"vendor":name,"materiality":f(v.get("avg_materiality")),"events":f(v.get("evidence_events"))})
    out=[]
    for a in ARCHS:
        item={**a,"layers":[],"evidence_strength":0,"vendor_count":0};vset=set();layer_scores=[];all_domains={d for l in a["layers"] for d in l["domains"]}
        for layer in a["layers"]:
            picks=[]
            for d in layer["domains"]:
                for x in sorted(by_domain.get(d,[]),key=lambda z:(z.get("materiality",0),z.get("events",0)),reverse=True)[:4]:
                    if x["vendor"] not in [p["vendor"] for p in picks]:picks.append({"vendor":x["vendor"],"domain":d,"evidence_strength":round(float(x.get("materiality") or 0),2)})
            for p in picks:vset.add(p["vendor"])
            domain_coverage=sum(1 for d in layer["domains"] if by_domain.get(d))/max(1,len(layer["domains"]));avg_mat=sum(p["evidence_strength"] for p in picks)/max(1,len(picks)) if picks else 0
            layer_score=clamp(.58*domain_coverage+.42*avg_mat);layer_scores.append(layer_score)
            item["layers"].append({**layer,"vendors":picks[:6],"coverage_score":round(layer_score,2)})
        top_integrators=[]
        for p in profiles:
            if p.get("entity_type")!="integrator":continue
            fit=len(set(p.get("technology_focus") or [])&all_domains)/max(1,min(4,len(all_domains)))
            if fit<=0:continue
            score=clamp(.40*fit+.24*(f(p.get("capability_score"))/100)+.20*(f(p.get("westcon_relevance"))/100)+.16*f(p.get("confidence")))
            top_integrators.append({"integrator":p.get("name"),"score":round(score,3),"capability":p.get("capability_score"),"relevance":p.get("westcon_relevance"),"evidence_grade":p.get("evidence_grade")})
        top_integrators.sort(key=lambda x:x["score"],reverse=True);top_integrators=top_integrators[:8]
        vendor_evidence=sum(layer_scores)/max(1,len(layer_scores));layer_coverage=sum(1 for x in layer_scores if x>=.45)/max(1,len(layer_scores));integrator_support=min(1,len(top_integrators)/5)
        evidence_strength=clamp(.46*vendor_evidence+.34*layer_coverage+.20*integrator_support)
        readiness=clamp(.46*evidence_strength+.28*integrator_support+.16*min(1,len(vset)/5)+.10*(1 if a.get("motions") else 0))
        gaps=[a["layers"][i]["name"] for i,s in enumerate(layer_scores) if s<.45]
        item["vendor_count"]=len(vset);item["integrator_count"]=len(top_integrators);item["top_integrators"]=top_integrators;item["layer_coverage"]=round(layer_coverage,2)
        item["evidence_strength"]=round(evidence_strength,2);item["commercial_readiness"]=round(readiness,2);item["evidence_gaps"]=gaps
        item["business_questions"]=["¿Qué integradores tienen capacidad demostrada para este play?","¿Qué fabricantes aportan la mayor complementariedad?","¿Qué servicios recurrentes puede adjuntar Westcon?","¿Qué gaps de enablement bloquean time-to-revenue?"]
        item["business_kpis"]=["Integradores activables","Pipeline del play","Attach de servicios","Tiempo hasta primera oportunidad","Cobertura de evidencias"]
        out.append(item)
    return {"meta":{"generated_at":iso_now(),"style":"Original analyst-style layered diagrams; no proprietary Gartner artwork is reproduced."},"architectures":out}
