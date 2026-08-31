from __future__ import annotations
import json,re,time,urllib.request,urllib.error,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse,urldefrag
ROOT=Path(__file__).resolve().parents[2]
UA='Westcon-Iberia-Decision-Intelligence/3.19 (+public-research; respectful)'
PATH_HINTS=['/','/marcas','/fabricantes','/vendors','/partners','/portfolio','/line-card','/soluciones','/solutions','/servicios','/services','/empresa','/sobre-nos','/quem-somos','/careers','/empleo','/emprego','/jobs','/sitemap.xml']
LINK_HINT=re.compile(r'(marca|fabric|vendor|partner|portfolio|line.?card|solu|servi|career|emple|emprego|job|pdf|catalog)',re.I)

def now(): return datetime.now(timezone.utc).isoformat()
def _load(path,default):
    p=ROOT/path
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return default

def _save(path,obj):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)

def _seed_entities():
    cfg=_load('config/current/distributor_research.json',{})
    data=_load('data/current/intelligence.json',{})
    seeds={}
    for row in data.get('distributors',[]):
        name=row.get('name'); candidates=[]
        for f in (row.get('fields') or {}).values():
            for e in f.get('evidence') or []:
                u=str(e.get('url') or '')
                if e.get('official') and u.startswith('http'):candidates.append(u)
        rec=cfg.get(name,{})
        u=(rec.get('source') or {}).get('url') or (candidates[0] if candidates else '')
        if u:seeds[name]={'url':u,'config':rec}
    for name,rec in cfg.items():
        u=(rec.get('source') or {}).get('url')
        if u:seeds.setdefault(name,{'url':u,'config':rec})
    return seeds

def fetch(url,deadline,cache,timeout=12,retries=2):
    key=hashlib.sha1(url.encode()).hexdigest();cached=cache.get(key)
    if cached and cached.get('ok') and time.time()-cached.get('ts',0)<86400:
        return {**cached,'cached':True}
    last=''
    for i in range(retries):
        remain=deadline-time.monotonic()
        if remain<=2:return {'ok':False,'url':url,'error':'deadline'}
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,application/xml,application/pdf;q=0.8,*/*;q=0.5'})
            with urllib.request.urlopen(req,timeout=max(2,min(timeout,remain-1))) as r:
                ct=r.headers.get('content-type','');body=r.read(2_500_000)
                text=body.decode('utf-8','ignore') if ('text' in ct or 'html' in ct or 'xml' in ct) else ''
                res={'ok':True,'url':r.geturl(),'status':getattr(r,'status',200),'content_type':ct,'text':text,'ts':time.time()};cache[key]=res;return res
        except urllib.error.HTTPError as e:
            last=f'HTTP {e.code}'
            if e.code in {401,403,404,410,429}:break
        except Exception as e:last=str(e)[:180]
        time.sleep(min(4,0.8*(2**i)))
    res={'ok':False,'url':url,'error':last or 'fetch failed','ts':time.time()};cache[key]=res;return res

def _discover(base,res):
    if not res.get('text'):return []
    host=urlparse(base).netloc.lower();out=[]
    for href in re.findall(r'''(?:href|loc)=["']?([^"'<>\s]+)|<loc>\s*([^<]+)</loc>''',res['text'],re.I):
        raw=next((x for x in href if x),'');u=urldefrag(urljoin(base,raw))[0]
        p=urlparse(u)
        if p.scheme in {'http','https'} and p.netloc.lower()==host and LINK_HINT.search(p.path):out.append(u)
    return list(dict.fromkeys(out))[:30]

def run(profile='daily',max_entities=None,max_runtime=600):
    seeds=_seed_entities();limits={'daily':12,'deep':35,'exhaustive':999};limit=max_entities or limits.get(profile,12)
    deadline=time.monotonic()+max(20,int(max_runtime));ledger=[];cache=_load('data/current/research_cache.json',{})
    learning=_load('data/current/research_learning.json',{'version':'3.19.0','strategies':{}});stats=learning.setdefault('strategies',{})
    entity_items=list(seeds.items())[:limit]
    stop_reason='complete';domains={}
    def checkpoint():
        _save('data/current/research_ledger.json',{'version':'3.19.0','profile':profile,'generated_at':now(),'queries_or_urls_checked':len(ledger),'stop_reason':stop_reason,'results':ledger[-500:]})
        _save('data/current/research_learning.json',learning)
        # Cache is internal/transient; bounded to avoid repo growth and never published by Pages.
        if len(cache)>1500:
            newest=sorted(cache.items(),key=lambda kv:kv[1].get('ts',0),reverse=True)[:1000];cache.clear();cache.update(newest)
        _save('data/current/research_cache.json',cache)
    for name,seed in entity_items:
        if time.monotonic()>=deadline-5:stop_reason='deadline';break
        p=urlparse(seed['url']);base=f'{p.scheme}://{p.netloc}';host=p.netloc.lower();state=domains.setdefault(host,{'failures':0,'circuit':False})
        queue=[urljoin(base,x) for x in PATH_HINTS[:(6 if profile=='daily' else len(PATH_HINTS))]];seen=set()
        while queue and time.monotonic()<deadline-4:
            u=queue.pop(0)
            if u in seen:continue
            seen.add(u)
            if state['circuit']:break
            res=fetch(u,deadline,cache,retries=1 if profile=='daily' else 2)
            ok=bool(res.get('ok'));family='official-domain'
            ledger.append({'entity':name,'url':u,'ok':ok,'status':res.get('status'),'error':res.get('error'),'cached':bool(res.get('cached')),'source_family':family,'researched_at':now()})
            st=stats.setdefault(family,{'attempts':0,'successes':0,'yield':0.0});st['attempts']+=1;st['successes']+=int(ok);st['yield']=round(st['successes']/max(1,st['attempts']),4)
            if ok:
                state['failures']=0
                if profile!='daily':
                    for x in _discover(u,res):
                        if x not in seen and x not in queue:queue.append(x)
            else:
                state['failures']+=1
                if state['failures']>=4:state['circuit']=True
            if len(ledger)%20==0:checkpoint()
            time.sleep(0.15)
        if time.monotonic()>=deadline-4:stop_reason='deadline';break
    learning['version']='3.19.0';learning['updated_at']=now();learning['policy']='yield-aware; official-domain first; weak job signals never promote relationships'
    checkpoint()
    return {'version':'3.19.0','profile':profile,'generated_at':now(),'queries_or_urls_checked':len(ledger),'successful_fetches':sum(1 for x in ledger if x['ok']),'stop_reason':stop_reason,'results':ledger}
