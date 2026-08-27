import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v31.taxonomy import classify_record
from v31.confidence import recommendation_threshold


def test_attackiq_awards_not_procurement():
    r=classify_record({'title':'AttackIQ Customer Awards 2026','summary':'Awards recognize customers and security leaders','url':'https://www.attackiq.com/awards'})
    assert r.classification != 'procurement_award'
    assert 'award' in r.classification


def test_real_procurement_award():
    r=classify_record({'title':'Contract award notice','contracting_authority':'Public Agency','notice_id':'123','cpv':'48000000','url':'https://ted.europa.eu/en/notice/123'})
    assert r.classification == 'procurement_award'


def test_strategic_thresholds_are_high():
    assert recommendation_threshold('strategic_priority') >= .85
    assert recommendation_threshold('partner_recruitment') >= .78
