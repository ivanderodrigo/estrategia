from __future__ import annotations
import concurrent.futures, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping
from .common import norm, uniq, parse_date, iso_now, f, clamp

TECH={
 "Cybersecurity":["cybersecurity","ciberseguridad","security","seguridad","soc","mssp","xdr","siem","firewall","zero trust"],
 "SASE/SSE":["sase","sse","ztna","secure access","swg","casb"],
 "Networking":["network","networking","redes","sd-wan","wifi","wi-fi","lan","wan"],
 "Cloud":["cloud","nube","azure","aws","google cloud","multicloud","hybrid cloud"],
 "Data Center":["data center","datacenter","centro de datos","servidor","storage","infraestructura"],
 "AI":["artificial intelligence","inteligencia artificial","generative ai","genai"," ia "," ai "],
 "Observability":["observability","observabilidad","monitoring","monitorización","monitorizacion","apm"],
 "Automation":["automation","automatización","automatizacion","orchestration","orquestación"],
 "Identity":["identity","identidad","iam","pam","mfa"]
}
VERTICALS={
 "Sector público":["sector público","sector publico","administración","administracion","gobierno","ministerio","ayuntamiento","public sector"],
 "Banca y seguros":["banca","bank","banking","seguros","insurance","financiero","financial"],
 "Industria":["industria","industrial","manufacturing","fabricación","fabricacion"],
 "Retail":["retail","comercio","tienda","ecommerce","e-commerce"],
 "Salud":["salud","health","healthcare","hospital","sanidad"],
 "Telecomunicaciones":["telecom","telco","telecommunications","operador"],
 "Energía y utilities":["energia","energía","utilities","utility","electricidad","agua"],
 "Transporte":["transport","transporte","logística","logistica","mobility","movilidad"]
}
SERVICE_TERMS={
 "SOC / seguridad gestionada":[" soc ","mssp","managed security","seguridad gestionada"],
 "NOC / red gestionada":[" noc ","managed network","red gestionada"],
 "Cloud gestionada":["managed cloud","cloud gestionada","cloud managed"],
 "Servicios profesionales":["professional services","servicios profesionales","consultoría","consultoria"],
 "Formación y enablement":["training","formación","formacion","academy","enablement"],
 "Financiación":["financing","financiación","financiacion","as-a-service","consumption model"],
 "Marketplace / plataforma":["marketplace","platform","plataforma"],
 "Staging / integración":["staging","configuración","configuracion","integration center","preconfiguración","preconfiguracion"]
}
FIELD_QUERIES={
 "distributor":[
   ("vendors",'(distribuidor OR distribución OR distribution OR mayorista OR "partner de canal")'),
   ("managed_services",'(SOC OR NOC OR MSSP OR "managed services" OR "servicios gestionados")'),
   ("value_added",'(formación OR training OR financiación OR financing OR staging OR marketplace OR "servicios profesionales")'),
   ("services",'("professional services" OR "servicios profesionales" OR lifecycle OR soporte OR support OR cloud OR ciberseguridad)'),
   ("channel_moves",'("nuevo distribuidor" OR "acuerdo de distribución" OR "distribution agreement" OR partnership OR adquisición OR expansion)')
 ],
 "integrator":[
   ("vendors",'(partner OR partnership OR certificación OR certification OR specialization OR especialización)'),
   ("certifications",'(certificación OR certification OR certified OR especialización OR specialization OR competency OR competence)'),
   ("managed_services",'(SOC OR NOC OR MSSP OR "managed services" OR "servicios gestionados" OR MDR OR XDR)'),
   ("customers",'("caso de éxito" OR "customer story" OR cliente OR customer OR proyecto OR despliegue OR implantación)'),
   ("verticals",'(banca OR seguros OR industria OR retail OR salud OR "sector público" OR telecomunicaciones OR energía OR transporte)'),
   ("services",'("servicios profesionales" OR consulting OR consultoría OR cloud OR ciberseguridad OR networking OR observabilidad OR automatización)')
 ]
}
FIELD_OUTPUT={
 "vendors":"vendors","certifications":"certifications","managed_services":"managed_services",
 "customers":"customer_cases","verticals":"verticals","services":"services","value_added":"value_added","channel_moves":"channel_moves"
}
# Fuente: heurística de autoridad; sirve para priorizar corroboración, no para afirmar veracidad por sí sola.
TIER_B={"computing bps","bps channel partner","muycanal","computerworld espana","computerworld españa","itreseller es","ituser es","channelbiz","interempresas","interempresas media","cinco dias","cinco días","expansion","expansión","el economista","jornal de negocios","observador","silicon"}


def _fetch(query:str, timeout:int=8, max_results:int=10):
    q=urllib.parse.quote(query)
    url=f"https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 Westcon-Iberia-Research/3.3.1"})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:data=r.read()
        root=ET.fromstring(data);out=[]
        for item in root.findall(".//item")[:max_results]:
            title=(item.findtext("title") or "").strip();link=(item.findtext("link") or "").strip();pub=(item.findtext("pubDate") or "").strip();source=item.find("source");src=(source.text or "").strip() if source is not None else "Google News"
            if title:out.append({"title":title,"url":link,"published_at":pub,"source":src,"provider":"google_news_rss"})
        return out,None
    except Exception as exc:return [],f"{type(exc).__name__}:{exc}"


def _aliases(name:str):
    n=norm(name);out={n}
    for suffix in (" spain"," espana"," portugal"," iberia"," global"):
        if n.endswith(suffix):out.add(n[:-len(suffix)].strip())
    # marcas con formato A / B
    if "/" in name:
        out.update(norm(x) for x in name.split("/") if norm(x))
    return {x for x in out if len(x)>=3}


def _contains_entity(title:str,name:str)->bool:
    t=" "+norm(title)+" "
    return any(re.search(r"(?:^|\s)"+re.escape(a)+r"(?:$|\s)",t.strip()) for a in _aliases(name))


def _contains_vendor(title:str,vendor:str)->bool:
    t=" "+norm(title)+" ";vn=norm(vendor)
    return bool(vn and re.search(r"(?:^|\s)"+re.escape(vn)+r"(?:$|\s)",t.strip()))


def _classify(title:str,known_vendors:list[str]):
    t=" "+norm(title)+" ";out={"technologies":[],"verticals":[],"services":[],"vendors":[]}
    for label,terms in TECH.items():
        if any(norm(x).strip() in t for x in terms):out["technologies"].append(label)
    for label,terms in VERTICALS.items():
        if any(norm(x).strip() in t for x in terms):out["verticals"].append(label)
    for label,terms in SERVICE_TERMS.items():
        if any(norm(x).strip() in t for x in terms):out["services"].append(label)
    for v in known_vendors:
        if _contains_vendor(title,v):out["vendors"].append(v)
    if any(x in t for x in ["certific","specialization","especializacion","competency","competence"]):out["certification_signal"]=True
    if any(x in t for x in ["cliente","customer","caso de exito","customer story","proyecto","despliegue","implantacion"]):out["customer_signal"]=True
    return out


def _source_grade(source:str,entity:str,vendors:list[str]):
    s=norm(source)
    if not s:return "D"
    if any(a and (s==a or a in s) for a in _aliases(entity)):return "A"
    if any(norm(v) and (s==norm(v) or norm(v) in s) for v in vendors):return "A"
    if any(x in s for x in TIER_B):return "B"
    if any(x in s for x in ["news","actualidad","magazine","revista","diario","economia","economía","business","tech","canal"]):return "C"
    return "C"


def _meaningful(v):
    if v in (None,"",0,[],{}):return False
    return True


def _field_has_data(profile:Mapping[str,Any],field:str)->bool:
    key=FIELD_OUTPUT.get(field,field)
    if field=="channel_moves":return f(profile.get("channel_moves"))>0
    if field=="customers":return bool(profile.get("customer_cases") or profile.get("customer_case_examples"))
    return _meaningful(profile.get(key))


def _profile_map(previous_profiles:Mapping[str,Any]|None):
    out={}
    if not isinstance(previous_profiles,Mapping):return out
    # v3.3.3: if the canonical flat collection exists, never append the two
    # convenience views again.  In 3.3.1/3.3.2 this triplicated scheduler input.
    rows=previous_profiles.get("profiles") or ((previous_profiles.get("distributors") or [])+(previous_profiles.get("integrators") or []))
    for x in rows:
        if x.get("name"):out[norm(x.get("name"))]=x
    return out


def _geo(country):
    if country in {"IBERIA","GLOBAL",None,""}:return '(España OR Spain OR Portugal OR Iberia)'
    if country=="ES":return '(España OR Spain)'
    if country=="PT":return '(Portugal)'
    return '(España OR Spain OR Portugal OR Iberia)'


def _build_jobs(entities,known_vendors,previous_profiles,priority_pairs,cfg,limit):
    pmap=_profile_map(previous_profiles);field_pr=cfg.get("field_priorities") or {}
    buckets={"distributor":defaultdict(list),"integrator":defaultdict(list)}
    for e in entities:
        et=e.get("entity_type") or e.get("type");name=e.get("name") or e.get("entity_name")
        if et not in FIELD_QUERIES or not name:continue
        prev=pmap.get(norm(name),{});coverage=f(prev.get("coverage_score"))/100
        evidence=f(prev.get("evidence_count"));tier=prev.get("entity_tier") or "T2";tier_w={"T1":1.35,"T2":1.0,"T3":.62}.get(tier,1.0)
        target=f(prev.get("coverage_target")) or (85 if et=="integrator" and tier=="T1" else 80 if et=="distributor" and tier=="T1" else 65 if tier=="T2" else 40)
        gap=max(0,target-f(prev.get("coverage_score")))/100;relevance=f(prev.get("westcon_relevance"))/100;biz=f(prev.get("activation_priority") or prev.get("competitive_response_priority"))/100
        for field,fragment in FIELD_QUERIES[et]:
            missing=not _field_has_data(prev or e,field)
            base=f(field_pr.get(field)) if field_pr.get(field) is not None else .78
            pr=base*tier_w*(1+(.62 if missing else .05)+.42*gap+.18*(1-coverage)+.12*relevance+.10*biz+(.10 if evidence<3 else 0))
            q=f'"{name}" {fragment} {_geo(e.get("country") or e.get("scope"))}'
            buckets[et][norm(name)].append({"name":name,"entity_type":et,"field":field,"query":q,"job_type":"field_gap","priority":round(pr,3),"missing_before":missing,"entity_tier":tier,"coverage_gap_before":round(gap*100,1)})
    # orden interno por gap más valioso
    for et in buckets:
        for k in buckets[et]:buckets[et][k].sort(key=lambda x:x["priority"],reverse=True)
    # Pair verification ocupa una cuota separada y se mezcla con integradores.
    pair_limit=max(0,int(limit*f((cfg.get("pair_verification_share") or {}).get("daily")) if (cfg.get("pair_verification_share") or {}).get("daily") is not None else .18))
    pair_jobs=[];seen=set()
    for x in priority_pairs or []:
        integrator=x.get("integrator");vendor=x.get("vendor")
        if not integrator or not vendor:continue
        k=(norm(integrator),norm(vendor))
        if k in seen:continue
        seen.add(k)
        score=f(x.get("research_priority_score") or x.get("priority_score") or x.get("whitespace_score"))
        if score>1:score/=100
        q=f'"{integrator}" "{vendor}" (partner OR certification OR certified OR specialization OR "case study" OR cliente OR customer) (España OR Spain OR Portugal OR Iberia)'
        pair_jobs.append({"name":integrator,"entity_type":"integrator","field":"vendor_pair_verification","query":q,"job_type":"pair_verification","vendor":vendor,"priority":1.05+.55*score,"missing_before":True})
    pair_jobs.sort(key=lambda x:x["priority"],reverse=True);pair_jobs=pair_jobs[:pair_limit]

    # Fair share + profundidad: una primera pasada cubre entidades distintas; la segunda reparte
    # el presupuesto restante entre dimensiones para que daily no se quede solo en "vendors".
    dist=deque(sorted(buckets["distributor"],key=lambda k:buckets["distributor"][k][0]["priority"],reverse=True))
    integ=deque(sorted(buckets["integrator"],key=lambda k:buckets["integrator"][k][0]["priority"],reverse=True))
    jobs=[];minimum_integrator_share=f(cfg.get("minimum_integrator_share")) if cfg.get("minimum_integrator_share") is not None else .68
    base_limit=max(0,limit-len(pair_jobs));broad_limit=max(1,int(base_limit*.75));i_count=d_count=0
    while len(jobs)<broad_limit and (dist or integ):
        choose_integrator=bool(integ) and (not dist or (i_count/max(1,i_count+d_count))<minimum_integrator_share)
        dq=integ if choose_integrator else dist
        key=dq.popleft();lst=buckets["integrator" if choose_integrator else "distributor"][key]
        if lst:
            jobs.append(lst.pop(0));i_count+=1 if choose_integrator else 0;d_count+=0 if choose_integrator else 1
        if lst:dq.append(key)
    # Profundización por dimensiones: penaliza campos ya muy seleccionados para cubrir certificaciones,
    # clientes, verticales, servicios gestionados y valor añadido además de portfolio.
    leftovers=[]
    for et in ("integrator","distributor"):
        for lst in buckets[et].values():leftovers.extend(lst)
    field_count=Counter(x.get("field") for x in jobs);entity_field={(norm(x.get("name")),x.get("field")) for x in jobs}
    while len(jobs)<base_limit and leftovers:
        best_i=max(range(len(leftovers)),key=lambda i:leftovers[i]["priority"]/(1+.48*field_count[leftovers[i]["field"]]))
        j=leftovers.pop(best_i);k=(norm(j.get("name")),j.get("field"))
        if k in entity_field:continue
        jobs.append(j);entity_field.add(k);field_count[j["field"]]+=1
    # Inserta pair verification de forma distribuida, no al final.
    if pair_jobs:
        merged=[];step=max(2,int(max(1,len(jobs))/max(1,len(pair_jobs))))
        pi=0
        for idx,j in enumerate(jobs):
            merged.append(j)
            if pi<len(pair_jobs) and (idx+1)%step==0:merged.append(pair_jobs[pi]);pi+=1
        merged.extend(pair_jobs[pi:]);jobs=merged[:limit]
    return jobs


def run_targeted_research(entities:list[Mapping[str,Any]],known_vendors:list[str],profile:str,policy:Mapping[str,Any],runtime_seconds:int,previous_profiles:Mapping[str,Any]|None=None,priority_pairs:list[Mapping[str,Any]]|None=None):
    cfg=policy.get("targeted_search",{});limit=int(cfg.get(f"{profile}_max_queries",180));workers=int(cfg.get("workers",10));timeout=int(cfg.get("timeout_seconds",8));max_results=int(cfg.get("max_results_per_query",10));fresh_days=int((cfg.get("fresh_days") or {}).get(profile,180))
    # Ajusta cuota de pair verification al perfil actual sin mutar policy.
    cfg=dict(cfg);pair_share=dict(cfg.get("pair_verification_share") or {});pair_share["daily"]=f(pair_share.get(profile)) if pair_share.get(profile) is not None else .18;cfg["pair_verification_share"]=pair_share
    jobs=_build_jobs(entities,known_vendors,previous_profiles,priority_pairs,cfg,limit)
    started=time.monotonic();deadline=started+max(5,runtime_seconds);rows=[];errors=[];stats_by_field=Counter();accepted_by_field=Counter();entities_seen=set();pair_queries=0
    planned_entities={norm(x.get("name")) for x in jobs if x.get("name")};planned_tiers=Counter(x.get("entity_tier") or "pair" for x in jobs)
    def one(j):
        r,err=_fetch(j["query"],timeout,max_results);return j,r,err
    ex=concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    pending={};it=iter(jobs)
    try:
        for _ in range(min(workers,len(jobs))):
            try:j=next(it)
            except StopIteration:break
            pending[ex.submit(one,j)]=j
        while pending and time.monotonic()<deadline:
            done,_=concurrent.futures.wait(pending,timeout=min(1,max(0,deadline-time.monotonic())),return_when=concurrent.futures.FIRST_COMPLETED)
            if not done:continue
            for fut in done:
                j=pending.pop(fut);stats_by_field[j["field"]]+=1;entities_seen.add(norm(j["name"]));pair_queries+=1 if j.get("job_type")=="pair_verification" else 0
                try:j,res,err=fut.result()
                except Exception as exc:res=[];err=f"{type(exc).__name__}:{exc}"
                if err:errors.append({"entity":j["name"],"field":j["field"],"error":err})
                else:
                    cutoff=datetime.now(timezone.utc)-timedelta(days=fresh_days)
                    for r in res:
                        if not _contains_entity(r["title"],j["name"]):continue
                        if j.get("vendor") and not _contains_vendor(r["title"],j["vendor"]):continue
                        d=parse_date(r.get("published_at"))
                        if d and d<cutoff:continue
                        c=_classify(r["title"],known_vendors);r.update(j);r.update(c);r["observed_at"]=iso_now();r["source_grade"]=_source_grade(r.get("source"),j["name"],c.get("vendors") or ([j.get("vendor")] if j.get("vendor") else []))
                        base_conf={"A":.84,"B":.74,"C":.62,"D":.52}.get(r["source_grade"],.58)
                        if j.get("vendor") and j["vendor"] in (c.get("vendors") or []):base_conf+=.05
                        r["confidence"]=round(clamp(base_conf),3);rows.append(r);accepted_by_field[j["field"]]+=1
                if time.monotonic()<deadline:
                    try:nj=next(it);pending[ex.submit(one,nj)]=nj
                    except StopIteration:pass
    finally:
        for fut in pending:fut.cancel()
        ex.shutdown(wait=False,cancel_futures=True)
    ded={}
    for r in rows:
        k=(norm(r.get("name")),norm(r.get("title")))
        if k not in ded or r.get("confidence",0)>ded[k].get("confidence",0):ded[k]=r
    return list(ded.values()),{
        "planned_queries":len(jobs),"attempted_queries":sum(stats_by_field.values()),"evidence_rows":len(ded),"errors":errors[:40],"runtime_seconds":round(time.monotonic()-started,2),
        "entities_touched":len(entities_seen),"unique_entities_planned":len(planned_entities),"planned_by_tier":dict(planned_tiers),"pair_verification_queries":pair_queries,"attempted_by_dimension":dict(stats_by_field),"accepted_by_dimension":dict(accepted_by_field),
        "source_grades":dict(Counter(x.get("source_grade") for x in ded.values()))
    }
