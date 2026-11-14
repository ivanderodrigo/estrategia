"""Claim-specific matching for cited topic documents and editorial topic names.

A named report proves its citation, not every forecast in the card. Composite
names are editorial groupings; matching a documented component proves only
that thematic grounding, not a standardized architecture or vendor deployment.
"""
import re
from urllib.parse import urlparse
from .model import canonical

PUBLISHERS = {'gartner': 'gartner.com', 'forrester': 'forrester.com', 'idc': 'idc.com',
              'nist': 'nist.gov', 'enisa': 'enisa.europa.eu', 'dell oro group': 'delloro.com',
              'cloudflare': 'cloudflare.com'}
TOPIC_ALIASES = {
 'sase': ['sase', 'secure access service edge', 'security service edge'],
 'zero trust': ['zero trust'],
 'identity': ['identity security', 'identity threat detection', 'access management', 'identity first'],
 'ai security': ['ai security', 'artificial intelligence security', 'ai trism', 'agent governance', 'security for ai'],
 'secops': ['secops', 'security operations center', 'security operations', 'managed detection and response', 'ctem'],
 'network': ['aiops', 'network automation', 'networking platforms', 'network platforms', 'networking vendors'],
 'campus': ['campus network', 'secure campus', 'enterprise wired and wireless lan', 'lan security'],
 'ot': ['cps protection', 'cyber physical systems', 'operational technology security', 'ot security'],
 'data center': ['cloud ai infrastructure', 'ai infrastructure', 'ai data center', 'data center fabric'],
 'observability': ['observability', 'digital employee experience', 'digital experience monitoring'],
 'naas': ['naas', 'network as a service', 'managed network services', 'managed networking'],
 'agentic': ['agentic automation', 'agentic ai', 'robotic process automation'],
 'data security': ['data security posture management', 'dspm', 'crypto agility', 'data security'],
 'cloud native': ['cnapp', 'cloud native application protection', 'cloud native security'],
 'sovereignty': ['sovereign cloud', 'digital sovereignty', 'global sovereignty', 'cloud sovereignty'],
 'lifecycle': ['professional services', 'managed services', 'it services', 'lifecycle services'],
}

def issuer(url):
    host=(urlparse(url).hostname or '').lower()
    return next((name for name,domain in PUBLISHERS.items() if host==domain or host.endswith('.'+domain)), '')

def aliases(name):
    n=canonical(name)
    keys=[]
    for key,triggers in {
        'sase':['sase','sse'], 'zero trust':['zero trust'], 'identity':['identity','itdr'],
        'ai security':['ai security'], 'secops':['secops','soc','xdr'],
        'network':['aiops','network platform','ai native networking'],
        'campus':['campus','secure lan'], 'ot':['ot ','cps','xiot'],
        'data center':['data center'], 'observability':['observability','digital experience'],
        'naas':['naas','managed networking'], 'agentic':['agentic'],
        'data security':['data security','dspm'], 'cloud native':['cloud native','cnapp'],
        'sovereignty':['sovereignty','sovereign'], 'lifecycle':['lifecycle','professional services'],
    }.items():
        if any(t in n for t in triggers):keys.append(key)
    return list(dict.fromkeys(a for k in keys for a in TOPIC_ALIASES[k]))

def contains(text, phrase):
    return bool(re.search(r'(?<![a-z0-9])'+re.escape(canonical(phrase))+r'(?![a-z0-9])', canonical(text)))

def topic_excerpt(claim, url, text):
    """Find evidence for a citation/name, tolerating publisher label prefixes."""
    field=claim.get('field'); value=canonical(claim.get('value')); text=canonical(text)
    if field=='name':
        host=(urlparse(url).hostname or '').lower()
        primary_domains=('cloudflare.com','uipath.com','microsoft.com','cisco.com','redhat.com',
                         'ibm.com','checkpoint.com','paloaltonetworks.com','extremenetworks.com')
        if not issuer(url) and not any(host==d or host.endswith('.'+d) for d in primary_domains):
            return ''
        for alias in aliases(claim.get('entity','')):
            match=re.search(r'(?<![a-z0-9])'+re.escape(alias)+r'(?![a-z0-9])',text)
            if match:
                return text[max(0,match.start()-160):match.end()+300]
        return ''
    if field not in {'sources','analyst_basis'}:return ''
    publisher=issuer(url)
    if not publisher or not value.startswith(publisher+' '):return ''
    title=value[len(publisher):].strip()
    # Publisher is presentation metadata, not part of the document's title.
    # Preserve numbers and report editions; no fuzzy number/forecast matching.
    if len(title)<12:return ''
    match=re.search(re.escape(title),text)
    if match:return text[max(0,match.start()-80):match.end()+160]
    return ''

def classify_topic(claim,url):
    if claim.get('section') not in {'trends','architectures'}:return ''
    field=claim.get('field'); context=claim.get('source_context','')
    if field in {'sources','analyst_basis'}:
        return 'VERIFIED_CITED_TOPIC_DOCUMENT' if topic_excerpt(claim,url,context) else ''
    if field=='name' and topic_excerpt(claim,url,context):
        return 'VERIFIED_TOPIC_COMPONENT'
    if field in {'observed','drivers','buyer_priorities','evolution','context','principles','limits'}:
        if issuer(url) and len(canonical(claim.get('value')).split())>=5 and contains(context,claim['value']):
            return 'VERIFIED_EXACT_TOPIC_STATEMENT'
    return ''
