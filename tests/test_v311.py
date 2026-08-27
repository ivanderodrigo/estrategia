import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v31.discovery import make_query, _dedupe_entities, _profile_limits


def test_query_site_filter_is_explicit_and_bounded():
    q=make_query('AttackIQ','awards',['attackiq.com','example.com','ignored.example'])
    assert 'site:attackiq.com' in q and 'site:example.com' in q
    assert 'ignored.example' not in q


def test_entity_dedupe():
    rows=[{'name':'Cisco','entity_type':'vendor','country':'GLOBAL'},{'name':'Cisco','entity_type':'vendor','country':'GLOBAL'}]
    assert len(_dedupe_entities(rows)) == 1


def test_daily_is_bounded():
    x=_profile_limits('daily')
    assert x['target_sources'] <= 2
    assert x['providers'] <= 2
