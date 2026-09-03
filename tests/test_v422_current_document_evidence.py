import json
import unittest
from pathlib import Path

from engine.knowledge_provenance import typed_evidence_sufficient
from engine.confidence import apply_confidence_model
from engine.westcon_current_evidence import apply_westcon_current_evidence

ROOT=Path(__file__).resolve().parents[1]


class CurrentWestconEvidenceV422(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'config/current/westcon_fy27_document_facts.json').read_text(encoding='utf-8'))

    def test_historical_westcon_document_remains_non_accrediting(self):
        ev={
            'source':'Westcon','title':'Old deck','date':'FY26','description':'old',
            'provenance_origin':'WESTCON_DOCUMENT','source_type':'westcon-document','official':True,
        }
        self.assertFalse(typed_evidence_sufficient(ev))

    def test_current_westcon_document_is_accrediting_only_with_owned_scope(self):
        ev=dict(self.cfg['document'])
        ev.update({'description':'current exact fact','field':'capabilities','item_value':'WAAP/WAF','atomic':True})
        self.assertTrue(typed_evidence_sufficient(ev))
        ev['westcon_claim_scope']='market-share'
        self.assertFalse(typed_evidence_sufficient(ev))
        ev=dict(self.cfg['document'])
        ev.update({'description':'unrelated third-party fact','field':'market_share','item_value':'42%','atomic':True})
        self.assertFalse(typed_evidence_sufficient(ev))

    def test_spain_portfolio_is_mirrored_to_portugal_and_checkpoint_is_additional(self):
        data={'meta':{},'manufacturers':[]}
        stats=apply_westcon_current_evidence(data,self.cfg)
        self.assertEqual(stats['portfolio_spain_rows'],36)
        idx={r['name']:r for r in data['manufacturers']}
        self.assertGreaterEqual(len(idx),37)
        self.assertTrue(idx['1Password']['fields']['westcon_spain']['value'])
        self.assertTrue(idx['1Password']['fields']['westcon_portugal']['value'])
        self.assertFalse(idx['Check Point']['fields']['westcon_spain']['value'])
        self.assertTrue(idx['Check Point']['fields']['westcon_portugal']['value'])

    def test_fy27_document_supports_exact_capability_but_not_adc(self):
        data={'meta':{},'manufacturers':[{'id':'mfr-f5','name':'F5','fields':{'capabilities':{'value':['ADC','WAAP/WAF'],'items':[{'value':'ADC','evidence':[]},{'value':'WAAP/WAF','evidence':[]}]}}}]}
        apply_westcon_current_evidence(data,self.cfg)
        f5=next(r for r in data['manufacturers'] if r['name']=='F5')
        items={x['value']:x for x in f5['fields']['capabilities']['items']}
        self.assertFalse(any(str(e.get('provenance_origin'))=='WESTCON_DOCUMENT_CURRENT' for e in items['ADC']['evidence']))
        self.assertTrue(any(str(e.get('provenance_origin'))=='WESTCON_DOCUMENT_CURRENT' for e in items['WAAP/WAF']['evidence']))
        apply_confidence_model(data)
        self.assertEqual(items['ADC']['confidence_band'], 'low')
        self.assertEqual(items['WAAP/WAF']['confidence_band'], 'high')

    def test_superseded_portugal_rule_is_corrected(self):
        data={'meta':{},'manufacturers':[{'name':'1Password','fields':{},'evidence':[{'note':'España y Portugal comparten el portfolio base. Portugal incorpora además Proofpoint y Check Point.'}]}]}
        apply_westcon_current_evidence(data,self.cfg)
        raw=json.dumps(data,ensure_ascii=False)
        self.assertNotIn('Proofpoint y Check Point',raw)
        self.assertIn('Portugal incorpora además Check Point',raw)


if __name__=='__main__':
    unittest.main()
