import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from v31.discovery import (
    make_query, _quality_filter, sanitize_signal, _semantic_dimension,
)
from v31.taxonomy import classify_record


def _task(name, country='PT', dim='customers', entity_type='integrator'):
    return {'ent': {'name': name, 'country': country, 'entity_type': entity_type}, 'dim': dim}


def test_country_specific_query_adds_geo_anchor():
    q = make_query('NTT DATA Portugal', 'customers', country='PT')
    # Full entity already contains Portugal, so no duplicate is required.
    assert 'NTT DATA' in q
    q2 = make_query('Axians', 'customers', country='PT')
    assert 'Portugal' in q2


def test_rejects_brazil_result_for_portugal_entity_without_local_anchor():
    row = {
        'title': 'Claranet compra Mandic, dobra equipe e quintuplica número de clientes - Forbes Brasil',
        'source': 'Forbes Brasil',
        'url': 'https://example.br/story',
        'published_at': 'Wed, 26 Aug 2026 10:00:00 GMT',
    }
    cleaned, reason = _quality_filter(row, _task('Claranet Portugal'), 'daily')
    assert cleaned is None
    assert reason == 'geo_relevance'


def test_exact_portugal_entity_allows_local_ma_and_reclassifies():
    row = {
        'title': 'NOS compra Claranet Portugal por 152 milhões - Observador',
        'source': 'Observador',
        'url': 'https://observador.pt/story',
        'published_at': 'Wed, 26 Aug 2026 10:00:00 GMT',
    }
    cleaned, reason = _quality_filter(row, _task('Claranet Portugal'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'ma'
    assert cleaned['semantic_reclassified'] is True


def test_customer_query_does_not_turn_leadership_news_into_customer_reference():
    row = {
        'title': 'NTT DATA anuncia Hugo Assis como novo head da área de Seguros - CQCS',
        'source': 'CQCS',
        'url': 'https://example.com/ntt-head',
        'published_at': 'Wed, 26 Aug 2026 10:00:00 GMT',
    }
    # No Portugal anchor -> reject rather than contaminate NTT DATA Portugal.
    cleaned, reason = _quality_filter(row, _task('NTT DATA Portugal'), 'daily')
    assert cleaned is None
    assert reason == 'geo_relevance'


def test_local_leadership_news_reclassifies_to_hiring():
    row = {
        'title': 'Joana Vilhena é a nova CMO da Devoteam Portugal - Marketeer',
        'source': 'Marketeer',
        'url': 'https://marketeer.sapo.pt/devoteam-portugal-cmo',
        'published_at': 'Wed, 26 Aug 2026 10:00:00 GMT',
    }
    cleaned, reason = _quality_filter(row, _task('Devoteam Portugal'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'hiring'


def test_awards_found_by_customer_query_reclassify_as_awards_not_procurement():
    row = {
        'title': 'São 59 os finalistas do Axians Portugal Digital Awards 2025 - Expresso',
        'source': 'Expresso',
        'url': 'https://expresso.pt/axians-awards',
        'published_at': 'Wed, 20 Aug 2025 10:00:00 GMT',
    }
    cleaned, reason = _quality_filter(row, _task('Axians Portugal'), 'daily')
    assert cleaned is None
    assert reason == 'owned_awards_program'


def test_real_customer_reference_stays_customer():
    row = {
        'title': 'Grupo Nabeiro inova com soluções da Claranet Portugal - Jornal de Negócios',
        'source': 'Jornal de Negócios',
        'url': 'https://www.jornaldenegocios.pt/claranet-nabeiro',
        'published_at': 'Wed, 26 Aug 2026 10:00:00 GMT',
    }
    cleaned, reason = _quality_filter(row, _task('Claranet Portugal'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'customers'


def test_daily_rejects_old_2023_story():
    row = {
        'title': 'NTT DATA Portugal apresenta soluções inovadoras no Sibos 2023',
        'source': 'Newsroom Lift',
        'url': 'https://example.pt/sibos-2023',
        'published_at': 'Mon, 18 Sep 2023 10:00:00 GMT',
    }
    cleaned, reason = _quality_filter(row, _task('NTT DATA Portugal'), 'daily')
    assert cleaned is None
    assert reason == 'stale'


def test_awards_guard_still_hard():
    r = classify_record({'title': 'AttackIQ Customer Awards 2026', 'url': 'https://attackiq.com/awards'})
    assert r.classification != 'procurement_award'


def test_sanitize_previous_low_quality_row_removes_it():
    row = {
        'entity_name': 'Axians Portugal',
        'entity_type': 'integrator',
        'country': 'PT',
        'dimension': 'customers',
        'title': 'Axians sob novo comando no Brasil - Baguete',
        'source': 'Baguete',
        'url': 'https://example.br/axians',
        'published_at': 'Wed, 26 Aug 2026 10:00:00 GMT',
    }
    cleaned, reason = sanitize_signal(row, 'daily')
    assert cleaned is None
    assert reason == 'geo_relevance'
