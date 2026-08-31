
from collections import Counter

def calculate(data,gaps,graph):
    secs=['manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures']
    ev=0;official=0;domains=set()
    for sec in secs:
        for row in data.get(sec,[]):
            for f in (row.get('fields') or {}).values():
                for e in f.get('evidence') or []:
                    ev+=1;official+=int(bool(e.get('official')))
                    u=e.get('url','')
                    if '://' in u: domains.add(u.split('/')[2].lower().removeprefix('www.'))
    return {'entities_total':sum(len(data.get(s,[])) for s in secs),'manufacturers':len(data.get('manufacturers',[])),'distributors':len(data.get('distributors',[])),'integrators':len(data.get('integrators',[])),'clients_public':len(data.get('clients_public',[])),'clients_private':len(data.get('clients_private',[])),'sources':len(data.get('source_catalog',[])),'domains_unique':len(domains),'evidences':ev,'official_evidences':official,'gaps_total':gaps['total_gaps'],'gaps_critical':gaps['critical_gaps'],'gaps_by_section':gaps['by_section'],'relations':len(graph['relationships']),'manufacturer_distributor_confirmed':sum(1 for r in graph['relationships'] if r['relation']=='distributes' and r['status']=='CONFIRMADO'),'manufacturer_integrator_confirmed':sum(1 for r in graph['relationships'] if r['relation']=='partners_with' and r['status']=='CONFIRMADO'),'client_technology_relations':sum(1 for r in graph['relationships'] if r['relation']=='technology_signal')}
