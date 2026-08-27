#!/usr/bin/env python3
from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v32.direct_sources import _alias_in_text, procurement_is_technology, _procurement_phase
from v32.event_intelligence import build_candidate_event, cluster_events
from v32.knowledge_graph import build_graph
from v32.decision_engine import build_decisions

W={x.casefold() for x in ['Cisco','Fortinet','Check Point','Palo Alto Networks','AWS','Microsoft Azure']}
T={'cisco':'vendor','fortinet':'vendor','indra':'integrator','atos spain':'integrator','td synnex':'distributor','exclusive networks':'distributor','mcr':'distributor'}

def ev(record,authority=.98,direct=True):
    r=dict(record);r.setdefault('published_at','2026-08-20T10:00:00+00:00');r.setdefault('source','Official');r.setdefault('url','https://example.com/x')
    return build_candidate_event(r,source_authority=authority,westcon_vendors=W,entity_types=T,direct=direct)

class V322Tests(unittest.TestCase):
    def test_atos_does_not_match_contratos(self):
        self.assertFalse(_alias_in_text('Atos','Contratos del Sector Público'))
        self.assertTrue(_alias_in_text('Atos','Adjudicatario: Atos Spain'))

    def test_mcr_short_alias_requires_token(self):
        self.assertFalse(_alias_in_text('MCR','Expediente XMCR22'))
        self.assertTrue(_alias_in_text('MCR','Proveedor MCR, S.L.'))

    def test_non_tech_procurement_rejected(self):
        self.assertFalse(procurement_is_technology({'title':'Mantenimiento de ascensores e instalaciones electromecánicas'}))
        self.assertFalse(procurement_is_technology({'title':'Suministro de productos farmacéuticos'}))
        self.assertFalse(procurement_is_technology({'title':'Construcción de dos muros de contención'}))

    def test_tech_procurement_accepted(self):
        self.assertTrue(procurement_is_technology({'title':'Servicio de operación, mantenimiento y monitorización de infraestructura de red y seguridad IT'}))
        self.assertTrue(procurement_is_technology({'title':'Suministro de ordenadores personales'}))
        self.assertTrue(procurement_is_technology({'title':'Servicio de desarrollo de software'}))

    def test_portuguese_aquisicao_is_procurement_not_ma(self):
        e=ev({'title':'Aquisição de equipamento informático diverso','entity_name':'Iberia Public Procurement Market','entity_type':'market','country':'PT','dimension':'procurement_notice','evidence_kind':'public_procurement','procurement_phase':'notice','technology_procurement':True,'buyer_name':'Universidade de Aveiro'})
        self.assertEqual(e['event_type'],'procurement_notice')

    def test_procurement_award_requires_structured_phase(self):
        self.assertEqual(_procurement_phase({'winner_name':'Atos Spain'}),'award')
        self.assertEqual(_procurement_phase({'notice_type':'cn-standard'}),'notice')
        self.assertEqual(_procurement_phase({'notice_type':'can-standard'}),'award')

    def test_market_procurement_notice_is_opportunity_with_priority(self):
        e=ev({'title':'Servicio de ciberseguridad y monitorización de red','entity_name':'Iberia Public Procurement Market','entity_type':'market','country':'ES','dimension':'procurement_notice','evidence_kind':'public_procurement','procurement_phase':'notice','technology_procurement':True,'buyer_name':'Ayuntamiento X'})
        d=build_decisions(cluster_events([e]),{'materiality_floor_recommendation':.45,'confidence_floor_recommendation':.5})
        self.assertTrue(d['decisions']);self.assertEqual(d['decisions'][0]['impact'],'opportunity');self.assertIn(d['decisions'][0]['priority'],{'P1','P2','P3','P4'})

    def test_completed_procurement_award_is_watch_not_opportunity(self):
        e=ev({'title':'Adjudicación del servicio de red','entity_name':'Atos Spain','entity_type':'integrator','country':'ES','dimension':'procurement_award','evidence_kind':'public_procurement','procurement_phase':'award','technology_procurement':True,'buyer_name':'Ministerio X','winner_name':'Atos Spain'})
        d=build_decisions(cluster_events([e]),{'materiality_floor_recommendation':.45,'confidence_floor_recommendation':.5})
        self.assertTrue(d['decisions']);self.assertEqual(d['decisions'][0]['impact'],'watch')

    def test_procurement_graph_uses_buyer_and_winner_labels(self):
        e=ev({'title':'Adjudicación del servicio de red','entity_name':'Atos Spain','entity_type':'integrator','country':'ES','dimension':'procurement_award','evidence_kind':'public_procurement','procurement_phase':'award','technology_procurement':True,'buyer_name':'Ministerio X','winner_name':'Atos Spain'})
        g=build_graph(cluster_events([e]));edge=g['edges'][0]
        self.assertEqual(edge['relation'],'AWARDED_CONTRACT_TO');self.assertEqual(edge['from_label'],'Ministerio X');self.assertEqual(edge['to_label'],'Atos Spain')

    def test_competitor_distribution_of_westcon_vendor_is_threat(self):
        e=ev({'title':'TD SYNNEX será distribuidor global de Fortinet','entity_name':'TD SYNNEX','entity_type':'distributor','country':'IBERIA','dimension':'distribution','object_entity':'Fortinet'},direct=False)
        # Ensure object flag is set via explicit object_entity extraction.
        d=build_decisions(cluster_events([e]),{'materiality_floor_recommendation':.45,'confidence_floor_recommendation':.45})
        self.assertTrue(d['decisions']);self.assertEqual(d['decisions'][0]['impact'],'threat')

    def test_decision_surfaces_sources_alias(self):
        e=ev({'title':'Cisco lanza nueva plataforma de seguridad','entity_name':'Cisco','entity_type':'vendor','country':'GLOBAL','dimension':'services'},direct=False)
        d=build_decisions(cluster_events([e]),{'materiality_floor_recommendation':.45,'confidence_floor_recommendation':.45})
        self.assertTrue(d['decisions']);self.assertTrue(d['decisions'][0]['sources']);self.assertGreaterEqual(d['decisions'][0]['source_count'],1)


    def test_ma_negotiation_is_rumor_not_acquisition(self):
        e=ev({'title':'El CEO de Palo Alto Networks negocia la compra de Okta','entity_name':'Palo Alto Networks','entity_type':'vendor','country':'GLOBAL','dimension':'ma'},direct=False)
        self.assertEqual(e['event_type'],'ma_rumor')

    def test_technology_alias_persisted(self):
        e=ev({'title':'Servicio de desarrollo de software y cloud','entity_name':'Iberia Public Procurement Market','entity_type':'market','country':'ES','dimension':'procurement_notice','evidence_kind':'public_procurement','procurement_phase':'notice','technology_procurement':True})
        self.assertEqual(e['technologies'],e['technology_domains'])
        self.assertTrue(e['technology_domains'])

    def test_tech_procurement_market_relevance_not_inflated_to_one(self):
        e=ev({'title':'Servicio de ciberseguridad y red','entity_name':'Iberia Public Procurement Market','entity_type':'market','country':'ES','dimension':'procurement_notice','evidence_kind':'public_procurement','procurement_phase':'notice','technology_procurement':True})
        self.assertLess(e['westcon_relevance'],.85)
        self.assertGreaterEqual(e['westcon_relevance'],.60)

if __name__=='__main__':unittest.main(verbosity=2)
