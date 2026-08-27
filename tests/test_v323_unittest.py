#!/usr/bin/env python3
from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v32.direct_sources import procurement_fit_score
from v32.event_intelligence import build_candidate_event, cluster_events
from v32.decision_engine import build_decisions
from v32.market_intelligence import build_competitive_pressure, build_whitespace_candidates

W={x.casefold() for x in ['Cisco','Fortinet','Check Point','Palo Alto Networks','AWS','Microsoft Azure']}
T={'cisco':'vendor','fortinet':'vendor','indra':'integrator','atos spain':'integrator','td synnex':'distributor','exclusive networks':'distributor','westcon-comstor':'distributor'}
POL={'materiality_floor_recommendation':.45,'confidence_floor_recommendation':.45}

def ev(record,authority=.98,direct=True):
    r=dict(record);r.setdefault('published_at','2026-08-20T10:00:00+00:00');r.setdefault('source','Official');r.setdefault('source_category','official');r.setdefault('url','https://example.com/x')
    return build_candidate_event(r,source_authority=authority,westcon_vendors=W,entity_types=T,direct=direct)

class V323Tests(unittest.TestCase):
    def test_strategic_procurement_fit_beats_generic_software(self):
        cyber=procurement_fit_score({'title':'Servicio de monitorización de red, ciberseguridad, SASE y SOC'})
        generic=procurement_fit_score({'title':'Servicio de desarrollo de software de gestión administrativa'})
        self.assertGreaterEqual(cyber,.75);self.assertLess(generic,.62)

    def test_generic_it_procurement_not_automatic_opportunity(self):
        r={'title':'Servicio de desarrollo de software administrativo','entity_name':'Iberia Public Procurement Market','entity_type':'market','country':'ES','dimension':'procurement_notice','evidence_kind':'public_procurement','procurement_phase':'notice','technology_procurement':True,'procurement_fit_score':.42,'buyer_name':'Ayuntamiento X'}
        e=ev(r);d=build_decisions(cluster_events([e]),POL)
        self.assertFalse(any(x['impact']=='opportunity' for x in d['decisions']))

    def test_strategic_network_procurement_can_be_opportunity(self):
        r={'title':'Servicio de red, firewall, SOC y monitorización de ciberseguridad','entity_name':'Iberia Public Procurement Market','entity_type':'market','country':'ES','dimension':'procurement_notice','evidence_kind':'public_procurement','procurement_phase':'notice','technology_procurement':True,'procurement_fit_score':.88,'buyer_name':'Ministerio X'}
        e=ev(r);d=build_decisions(cluster_events([e]),POL)
        self.assertTrue(d['decisions']);self.assertEqual(d['decisions'][0]['impact'],'opportunity')
        self.assertIn('economic_priority_score',d['decisions'][0]);self.assertIn(d['decisions'][0]['economic_potential'],{'HIGH','MEDIUM','LOW'})

    def test_kev_is_not_unconditionally_opportunity(self):
        e=ev({'title':'CVE-2026-1: Cisco IOS explotación conocida','entity_name':'Cisco','entity_type':'vendor','country':'GLOBAL','dimension':'known_exploited_vulnerability','product':'IOS','cve':'CVE-2026-1'},direct=True)
        e['strategic_fit']=.55;e['materiality']=.70;e['confidence']=.90
        d=build_decisions([e],POL)
        self.assertTrue(d['decisions']);self.assertEqual(d['decisions'][0]['impact'],'watch')

    def test_competitor_distribution_builds_pressure(self):
        e=ev({'title':'TD SYNNEX será distribuidor de Fortinet en Iberia','entity_name':'TD SYNNEX','entity_type':'distributor','country':'IBERIA','dimension':'distribution','object_entity':'Fortinet'},direct=False)
        e=cluster_events([e])[0]
        p=build_competitive_pressure([e])
        self.assertTrue(p['entities']);self.assertEqual(p['entities'][0]['entity_name'],'TD SYNNEX')

    def test_whitespace_is_research_candidate_not_asserted(self):
        rows=[]
        rows.append(ev({'title':'Cisco lanza plataforma de networking cloud','entity_name':'Cisco','entity_type':'vendor','country':'GLOBAL','dimension':'services'},direct=False))
        rows.append(ev({'title':'Indra amplía servicios de networking y cloud','entity_name':'Indra','entity_type':'integrator','country':'ES','dimension':'services'},direct=False))
        rows.append(ev({'title':'Indra desarrolla nueva capacidad cloud networking','entity_name':'Indra','entity_type':'integrator','country':'ES','dimension':'competitive'},direct=False))
        out=build_whitespace_candidates(cluster_events(rows),W)
        if out['candidates']:
            self.assertEqual(out['candidates'][0]['status'],'RESEARCH_CANDIDATE_NOT_ASSERTED')

if __name__=='__main__':unittest.main(verbosity=2)
