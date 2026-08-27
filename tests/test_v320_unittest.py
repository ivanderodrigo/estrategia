#!/usr/bin/env python3
from __future__ import annotations
import json,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v32.event_intelligence import build_candidate_event, classify_event, cluster_events, detect_scope
from v32.knowledge_graph import build_graph
from v32.decision_engine import build_decisions

W={x.casefold() for x in ['Cisco','Fortinet','Check Point','Palo Alto Networks','AWS','Microsoft Azure']}
T={'cisco':'vendor','fortinet':'vendor','indra':'integrator','bechtle spain':'integrator','td synnex':'distributor'}

def ev(title, entity='Cisco', dimension='competitive', country='GLOBAL', source='Test', authority=.8):
    r={'title':title,'entity_name':entity,'entity_type':T.get(entity.casefold(),'vendor'),'dimension':dimension,'country':country,'source':source,'url':'https://example.com/'+str(abs(hash(title))),'published_at':'2026-08-20T10:00:00+00:00'}
    return build_candidate_event(r,source_authority=authority,westcon_vendors=W,entity_types=T,direct=False)

class V320Tests(unittest.TestCase):
    def test_buy_rating_not_ma(self):
        t='Bechtle AG: obtiene una recomendación de compra de Jefferies'
        self.assertNotEqual(classify_event({'title':t,'dimension':'ma'})[0],'ma_acquisition')
    def test_real_acquisition(self):
        self.assertEqual(classify_event({'title':'CrowdStrike adquiere Onum'})[0],'ma_acquisition')
    def test_procurement(self):
        self.assertEqual(classify_event({'title':'Adjudicación del contrato público a Indra'})[0],'procurement_award')
    def test_partner_award_not_procurement(self):
        self.assertEqual(classify_event({'title':'Indra recibe AWS Partner of the Year'})[0],'award')
    def test_distribution_award_is_award(self):
        self.assertEqual(classify_event({'title':'Fortinet nombra a Arrow Distribuidor del Año en España'})[0],'award')
    def test_distribution_agreement(self):
        self.assertEqual(classify_event({'title':'Exclusive Networks será distribuidor global de Fortinet'})[0],'distribution_agreement')
    def test_partnership(self):
        self.assertEqual(classify_event({'title':'Nokia, SAP y Microsoft firman un acuerdo estratégico plurianual'})[0],'partnership')
    def test_product_release(self):
        self.assertEqual(classify_event({'title':'Palo Alto Networks lanza PAN-OS 12.2 Ceres'})[0],'product_release')
    def test_outage(self):
        self.assertEqual(classify_event({'title':'Usuarios de Proofpoint reportan interrupciones del servicio'})[0],'operational_incident')
    def test_financial_results(self):
        self.assertEqual(classify_event({'title':'Nokia supera el BPA previsto en el segundo trimestre gracias a las ventas de IA'})[0],'financial_performance')
    def test_earnings_noise(self):
        typ,conf,reason=classify_event({'title':'Earnings To Watch: Cisco Reports Q2 Results Tomorrow'})
        self.assertEqual(typ,'financial_performance');self.assertEqual(reason,'market_noise')
    def test_third_party_certification(self):
        typ,_,reason=classify_event({'title':'50 estudiantes se forman para obtener su certificación Salesforce junto con NTT DATA'})
        self.assertNotEqual(typ,'certification');self.assertEqual(reason,'third_party_certification')
    def test_scope_spain(self):self.assertEqual(detect_scope({'title':'Nuevo servicio de Cisco en España'})[0],'ES')
    def test_scope_portugal(self):self.assertEqual(detect_scope({'title':'Claranet cresce em Portugal'})[0],'PT')
    def test_scope_other_region(self):self.assertEqual(detect_scope({'title':'Licitación 5G en Costa Rica favorece a Cisco'})[0],'OTHER_REGION')
    def test_other_region_relevance_low(self):
        e=ev('Licitación 5G en Costa Rica favorece a Cisco',dimension='procurement')
        self.assertLess(e['westcon_relevance'],.5)
    def test_meta_azure_cluster(self):
        a=ev('Meta se convierte en uno de los mayores clientes de IA de Microsoft Azure',entity='Microsoft Azure',dimension='customers',source='A')
        b=ev('Meta se convierte en uno de los principales clientes de IA de Microsoft Azure',entity='Microsoft Azure',dimension='customers',source='B')
        c=cluster_events([a,b]);self.assertEqual(len(c),1);self.assertEqual(c[0]['corroboration_count'],2)
    def test_accenture_edge_cluster(self):
        a=ev('Accenture lanza Accenture Edge para acelerar la adopción de IA en la mediana empresa',entity='Accenture Spain',dimension='services',source='A')
        b=ev('Accenture lanza su nueva línea de negocio Accenture Edge',entity='Accenture Spain',dimension='services',source='B')
        c=cluster_events([a,b]);self.assertEqual(len(c),1)
    def test_graph_edge(self):
        e=ev('Exclusive Networks será distribuidor global de Fortinet',entity='Fortinet',dimension='distribution')
        es=cluster_events([e]);g=build_graph(es);self.assertGreaterEqual(len(g['edges']),1)
    def test_minority_stake_is_investment(self):
        self.assertEqual(classify_event({'title':'Nokia adquiere el 11% de Inseego'})[0],'investment')

    def test_meta_azure_is_customer_reference(self):
        self.assertEqual(classify_event({'title':'Meta se convierte en uno de los mayores clientes de IA de Microsoft Azure'})[0],'customer_reference')

    def test_future_tense_product_release(self):
        self.assertEqual(classify_event({'title':'Nokia lanzará la primera plataforma RAN comercial nativa de IA'})[0],'product_release')

    def test_joint_solution_launch_is_product_release(self):
        self.assertEqual(classify_event({'title':'Accenture y Google Cloud lanzan soluciones de IA para empresas medianas'})[0],'product_release')

    def test_vendor_deploys_own_stack_not_customer(self):
        typ=classify_event({'title':'Cisco despliega su gran apuesta agéntica: red, seguridad y operaciones bajo un control unificado','dimension':'customers'})[0]
        self.assertNotEqual(typ,'customer_reference')

    def test_old_event_materiality_is_penalized(self):
        recent=ev('Exclusive Networks será distribuidor global de Fortinet',entity='Fortinet',dimension='distribution',authority=.98)
        old=dict(recent); old['published_at']='2023-01-01T00:00:00+00:00'
        from v32.event_intelligence import build_candidate_event
        old=build_candidate_event(old,source_authority=.98,westcon_vendors=W,entity_types=T,direct=True)
        rr=cluster_events([recent])[0]; oo=cluster_events([old])[0]
        self.assertGreater(rr['materiality'],oo['materiality'])

    def test_decisions_threshold(self):
        e=ev('Exclusive Networks será distribuidor global de Fortinet',entity='Fortinet',dimension='distribution',authority=.98)
        e['direct_evidence']=True
        es=cluster_events([e]);d=build_decisions(es,{'materiality_floor_recommendation':.5,'confidence_floor_recommendation':.5})
        self.assertGreaterEqual(len(d['decisions']),1)

if __name__=='__main__':unittest.main(verbosity=2)
