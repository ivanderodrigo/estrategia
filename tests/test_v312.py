import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v31.discovery import make_query, _dedupe_entities, _profile_limits, _entity_aliases, _is_relevant, _fair_gaps


def test_query_uses_or_not_long_implicit_and_chain():
    q=make_query('Cisco','distribution')
    assert ' OR ' in q
    assert '"Cisco"' in q


def test_query_site_filter_is_explicit_and_bounded():
    q=make_query('AttackIQ','awards',['attackiq.com','example.com','ignored.example'])
    assert 'site:attackiq.com' in q and 'site:example.com' in q
    assert 'ignored.example' not in q


def test_entity_aliases_strip_country_and_split_multibrand():
    assert 'NTT DATA' in _entity_aliases('NTT DATA Spain')
    aliases=_entity_aliases('V-Valley / Esprinet')
    assert 'V-Valley' in aliases and 'Esprinet' in aliases


def test_relevance_accepts_countryless_alias():
    row={'title':'NTT DATA expands cybersecurity services in Europe','url':'https://example.com/x'}
    assert _is_relevant(row,'NTT DATA Spain')


def test_entity_dedupe():
    rows=[{'name':'Cisco','entity_type':'vendor','country':'GLOBAL'},{'name':'Cisco','entity_type':'vendor','country':'GLOBAL'}]
    assert len(_dedupe_entities(rows)) == 1


def test_daily_is_bounded_and_parallel():
    x=_profile_limits('daily')
    assert x['target_sources'] <= 2
    assert x['providers'] <= 2
    assert 2 <= x['workers'] <= 6


def test_fair_gaps_first_round_spreads_entities():
    dims={'vendor':['a','b'],'integrator':['x','y'],'distributor':['d','e']}
    ents=[
        {'name':'A','entity_type':'vendor','country':'GLOBAL'},
        {'name':'B','entity_type':'integrator','country':'ES'},
        {'name':'C','entity_type':'distributor','country':'IBERIA'},
    ]
    pairs=_fair_gaps(ents,dims)
    assert [x[0]['name'] for x in pairs[:3]] == ['A','B','C']
