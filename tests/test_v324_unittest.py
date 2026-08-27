#!/usr/bin/env python3
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

from v32.direct_sources import atom_feed
from v32.market_intelligence import build_competitive_pressure, build_whitespace_candidates
from v32.decision_engine import build_briefing

ATOM=b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Servicio de monitorizacion de red y seguridad IT</title>
    <updated>2026-08-27T08:00:00Z</updated>
    <summary>Servicio de networking, firewall y monitorizacion</summary>
    <link href="https://example.invalid/tender/1" />
  </entry>
</feed>'''

class V324Tests(unittest.TestCase):
    def setUp(self):
        self.registry=[{'id':'placsp','name':'PLACSP','category':'official','authority':.99}]
        self.entities=[{'name':'Atos Spain','entity_type':'integrator','country':'ES'}]
        self.conn={'id':'placsp_atom','source_id':'placsp','kind':'atom_feed','url':'https://example.invalid/feed.atom','country':'ES','authority':.99}

    def test_atom_feed_no_nameerror_and_fit(self):
        with tempfile.TemporaryDirectory() as td, patch('v32.direct_sources._request',return_value=ATOM):
            rows,stats=atom_feed(self.conn,self.registry,self.entities,timeout=1,state_dir=Path(td),profile='daily')
        self.assertEqual(stats['successful'],1)
        self.assertEqual(len(rows),1)
        self.assertGreaterEqual(rows[0]['procurement_fit_score'],.62)
        self.assertEqual(rows[0]['dimension'],'procurement_notice')

    def test_atom_feed_uses_last_good_cache(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)
            with patch('v32.direct_sources._request',return_value=ATOM):
                rows,_=atom_feed(self.conn,self.registry,self.entities,timeout=1,state_dir=state,profile='daily')
            self.assertTrue(rows)
            with patch('v32.direct_sources._request',side_effect=TimeoutError('temporary')):
                cached,stats=atom_feed(self.conn,self.registry,self.entities,timeout=1,state_dir=state,profile='daily')
            self.assertTrue(cached)
            self.assertEqual(stats.get('cached'),1)
            self.assertTrue(cached[0].get('cache_fallback'))

    def test_competitive_pressure_exposes_alert_counts(self):
        events=[
            {'entity_name':'Competitor Dist','entity_type':'distributor','event_type':'distribution_agreement','market_scope':'IBERIA','materiality':.9,'confidence':.9,'strategic_fit':.9,'technology_domains':['Cybersecurity'],'title':'x','event_id':'1'},
            {'entity_name':'Competitor Dist','entity_type':'distributor','event_type':'managed_service','market_scope':'ES','materiality':.9,'confidence':.9,'strategic_fit':.9,'technology_domains':['Cybersecurity'],'title':'y','event_id':'2'},
        ]
        out=build_competitive_pressure(events)
        self.assertGreaterEqual(out['meta']['high_pressure'],1)
        self.assertTrue(out['alerts'])
        self.assertEqual(out['alerts'][0]['alert_type'],'competitive_threat')

    def test_whitespace_has_shortlist_not_assertion(self):
        events=[]
        for i in range(4):
            events.append({'entity_name':'Integrator X','entity_type':'integrator','event_type':'service_launch','technology_domains':['Cybersecurity'],'title':f'i{i}'})
            events.append({'entity_name':'Vendor X','entity_type':'vendor','event_type':'product_release','technology_domains':['Cybersecurity'],'title':f'v{i}'})
        out=build_whitespace_candidates(events,{'vendor x'})
        self.assertTrue(out['candidates'])
        self.assertIn(out['candidates'][0]['status'],{'RESEARCH_CANDIDATE_NOT_ASSERTED'})
        self.assertIn('shortlist',out)

    def test_briefing_reports_economic_distribution(self):
        decisions={'decisions':[{'impact':'watch','priority':'P3','economic_potential':'MEDIUM','economic_priority_score':.61,'evidence_grade':'A','source_count':1}]}
        b=build_briefing([],decisions)['headline_metrics']
        self.assertEqual(b['medium_economic_potential'],1)
        self.assertEqual(b['max_economic_priority_score'],.61)
        self.assertEqual(b['strong_evidence_decisions'],1)

if __name__=='__main__': unittest.main()
