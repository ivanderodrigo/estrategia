#!/usr/bin/env python3
from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v32.event_intelligence import build_candidate_event, classify_event, cluster_events
from v32.knowledge_graph import build_graph
from v32.decision_engine import build_decisions
from v32.direct_sources import _ted_country_queries

W={x.casefold() for x in ['Cisco','Fortinet','Check Point','Palo Alto Networks','AWS','Microsoft Azure']}
T={'cisco':'vendor','fortinet':'vendor','indra':'integrator','td synnex':'distributor','exclusive networks':'distributor'}

def ev(record, authority=.9, direct=True):
    r=dict(record);r.setdefault('published_at','2026-08-20T10:00:00+00:00');r.setdefault('source','Test');r.setdefault('url','https://example.com/x')
    return build_candidate_event(r,source_authority=authority,westcon_vendors=W,entity_types=T,direct=direct)

class V321Tests(unittest.TestCase):
    def test_ted_bulk_queries_only_two(self):
        q=_ted_country_queries('daily')
        self.assertEqual(len(q),2)
        self.assertIn('buyer-country = ESP',q[0][1]);self.assertIn('buyer-country = PRT',q[1][1])
    def test_structured_procurement_object_is_buyer(self):
        e=ev({'title':'Adjudicación de contrato a Indra','entity_name':'Indra','entity_type':'integrator','country':'ES','dimension':'procurement','buyer_name':'Ministerio de Justicia','winner_name':'Indra'})
        self.assertEqual(e['event_type'],'procurement_award');self.assertEqual(e['object_entity'],'Ministerio de Justicia')
    def test_kev_dimension_is_distinct(self):
        e=ev({'title':'CVE-2026-1234: Cisco IOS · explotación conocida (CISA KEV)','summary':'Known exploited vulnerability','entity_name':'Cisco','entity_type':'vendor','country':'GLOBAL','dimension':'known_exploited_vulnerability','product':'IOS','cve':'CVE-2026-1234'})
        self.assertEqual(e['event_type'],'known_exploited_vulnerability');self.assertIn('CVE-2026-1234',e['object_entity'])
    def test_kev_graph_edge(self):
        e=ev({'title':'CVE-2026-1234: Cisco IOS · explotación conocida (CISA KEV)','entity_name':'Cisco','entity_type':'vendor','country':'GLOBAL','dimension':'known_exploited_vulnerability','product':'IOS','cve':'CVE-2026-1234'})
        g=build_graph(cluster_events([e]));self.assertEqual(g['edges'][0]['relation'],'AFFECTED_BY_KEV')
    def test_kev_can_create_actionable_opportunity(self):
        e=ev({'title':'CVE-2026-1234: Cisco IOS · explotación conocida (CISA KEV)','entity_name':'Cisco','entity_type':'vendor','country':'GLOBAL','dimension':'known_exploited_vulnerability','product':'IOS','cve':'CVE-2026-1234'},authority=.99,direct=True)
        d=build_decisions(cluster_events([e]),{'materiality_floor_recommendation':.5,'confidence_floor_recommendation':.5})
        self.assertTrue(d['decisions']);self.assertEqual(d['decisions'][0]['impact'],'opportunity')

if __name__=='__main__': unittest.main(verbosity=2)
