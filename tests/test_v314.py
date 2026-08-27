import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from v31.discovery import _quality_filter, sanitize_signal
from v31.taxonomy import classify_record


def _task(name, country='ES', dim='customers', entity_type='integrator'):
    return {'ent': {'name': name, 'country': country, 'entity_type': entity_type}, 'dim': dim}


def _row(title, source='Test', url='https://example.com/x', published='Wed, 26 Aug 2026 10:00:00 GMT'):
    return {'title': title, 'source': source, 'url': url, 'published_at': published}


def test_scc_interview_is_market_signal_not_ma():
    r = classify_record(_row('Arturo Moncada, director general de SCC España: «Nadie se levanta pensando en comprar un servidor»'))
    assert r.classification == 'market_signal'


def test_hbx_ayesa_collaboration_is_customer_reference():
    cleaned, reason = _quality_filter(
        _row('HBX lanzan un canal de voz impulsado por IA para mejorar la atención del cliente, en colaboración con Ayesa'),
        _task('Ayesa', dim='services'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'customers'


def test_seidor_strategy_is_competitive_not_services():
    cleaned, reason = _quality_filter(
        _row('Seidor lanza un plan estratégico para alcanzar los 2.000 millones en ingresos en 2030 de la mano de Carlyle'),
        _task('SEIDOR', dim='services'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'competitive'
    assert cleaned['classification'] == 'strategy_growth'


def test_econocom_specialisation_is_services_not_certification():
    cleaned, reason = _quality_filter(
        _row('Econocom España se reestructura en cuatro áreas de especialización'),
        _task('Econocom Spain', dim='certification'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'services'
    assert cleaned['classification'] == 'capability_change'


def test_loan_contracting_is_not_hiring():
    cleaned, reason = _quality_filter(
        _row('Minsait (Indra) facilita con IA la contratación de préstamos por WhatsApp'),
        _task('Indra', dim='hiring'), 'daily')
    assert cleaned is None
    assert reason == 'semantic_mismatch'


def test_dmi_procurement_director_is_leadership_not_ma():
    cleaned, reason = _quality_filter(
        _row('DMI Computer pone a Javier Martín al frente del área de Compras'),
        _task('DMI Computer', dim='ma'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'hiring'
    assert cleaned['classification'] == 'leadership_change'


def test_soc_does_not_match_socios():
    cleaned, reason = _quality_filter(
        _row('Fortinet reconoció a sus socios con mejor desempeño en América Latina en 2025'),
        _task('Fortinet', country='GLOBAL', dim='services', entity_type='vendor'), 'daily')
    assert cleaned is None
    assert reason == 'geo_relevance'


def test_distributor_of_year_is_award_not_distribution():
    cleaned, reason = _quality_filter(
        _row('Fortinet nombra a Arrow Distribuidor del año en España'),
        _task('Fortinet', country='GLOBAL', dim='distribution', entity_type='vendor'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'awards'
    assert cleaned['classification'] == 'partner_award'


def test_global_distributor_remains_distribution():
    cleaned, reason = _quality_filter(
        _row('TD SYNNEX, seleccionada como distribuidor global de Fortinet'),
        _task('Fortinet', country='GLOBAL', dim='distribution', entity_type='vendor'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'distribution'


def test_axians_owned_awards_program_is_rejected():
    cleaned, reason = _quality_filter(
        _row('São 59 os finalistas do Axians Portugal Digital Awards 2025', source='Expresso', url='https://expresso.pt/x'),
        _task('Axians Portugal', country='PT', dim='awards'), 'daily')
    assert cleaned is None
    assert reason == 'owned_awards_program'


def test_student_certification_does_not_prove_ntt_certification():
    cleaned, reason = _quality_filter(
        _row('Alrededor de 50 estudiantes de los campus 42 se forman para obtener su certificación en Salesforce junto con NTT DATA', source='Fundación Telefónica España'),
        _task('NTT DATA Spain', country='ES', dim='certification'), 'daily')
    assert cleaned is None
    assert reason == 'third_party_certification'


def test_td_synnex_quote_is_market_signal_not_distribution():
    cleaned, reason = _quality_filter(
        _row('Jorge Llaurado, TD SYNNEX: “La distinción entre distribuidor tecnológico y financiero irá difuminándose hasta desaparecer”', source='itreseller.es'),
        _task('TD SYNNEX', country='IBERIA', dim='distribution', entity_type='distributor'), 'daily')
    assert reason is None
    assert cleaned['dimension'] == 'competitive'
    assert cleaned['classification'] == 'market_signal'


def test_historical_context_is_not_current_daily():
    cleaned, reason = _quality_filter(
        _row('CrowdStrike compra Onum', published='Thu, 28 Aug 2025 07:00:00 GMT'),
        _task('CrowdStrike', country='GLOBAL', dim='ma', entity_type='vendor'), 'daily')
    assert reason is None
    assert cleaned['freshness_band'] == 'historical_context'
    assert cleaned['is_current_signal'] is False


def test_recent_signal_is_current_daily():
    cleaned, reason = _quality_filter(
        _row('CrowdStrike adquiere Example Security'),
        _task('CrowdStrike', country='GLOBAL', dim='ma', entity_type='vendor'), 'daily')
    assert reason is None
    assert cleaned['freshness_band'] == 'current'
    assert cleaned['is_current_signal'] is True


def test_awards_guard_still_hard():
    r = classify_record({'title': 'AttackIQ Customer Awards 2026', 'url': 'https://attackiq.com/awards'})
    assert r.classification != 'procurement_award'
