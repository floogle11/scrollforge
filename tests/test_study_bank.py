from collections import Counter
from copy import deepcopy
import pytest

from worker.study_bank import build_bank
from worker.run_pipeline import validate_feed
from worker.ingest_nhl import parse_article
from worker.ingest_rss import normalize_entry


def test_bank_is_diverse_reproducible_and_contract_valid():
    cards = build_bank()
    assert cards == build_bank()
    assert len(cards) == 412
    assert sum(bool(card.get('quiz')) for card in cards) == 392
    assert len({card['id'] for card in cards}) == len(cards)
    assert len({card['body_markdown'] for card in cards}) == len(cards)
    counts = Counter(card['course_tag'] for card in cards)
    assert set(counts) == {'ME-3310', 'ENGR-2300', 'ME-3140', 'ME-3010', 'ME-2010', 'CALC-I', 'CALC-II', 'CALC-III', 'LINEAR-ALG', 'DIFF-EQ', 'PHYS-I', 'PHYS-II'}
    assert min(counts.values()) >= 16
    for course in ['CALC-I', 'CALC-II', 'CALC-III', 'PHYS-I', 'PHYS-II']:
        assert counts[course] == 32
    validate_feed({'last_updated': '2026-10-25T00:00:00Z', 'calendar_mode': 'BASELINE',
                   'active_exam_course': None, 'cards': cards})
    for card in cards:
        assert card['diagram']
        if not card.get('quiz'):
            assert card['category'] == 'DEEP_CUT'
            continue
        assert 4 <= len(card['quiz']['options']) <= 8
        assert len(set(card['quiz']['options'])) == len(card['quiz']['options'])
        assert len(card['body_markdown'].split()) <= 75
        assert 2 <= len(card['solution_markdown'].splitlines()) <= 4


@pytest.mark.parametrize('identity, answer', [
    ('study_continuity_0', '1.592 m/s'),
    ('study_carnot_engine_0', '50 %'),
    ('study_moment_0', '4 N·m'),
    ('study_principal_stress_0', '56.06 MPa'),
    ('study_rc_time_0', '1 s'),
    ('study_pump_power_0', '0.981 kW'),
    ('study_calc1_limit_0', '4'),
    ('study_calc1_power_0', '12'),
    ('study_calc1_chain_0', '6'),
    ('study_calc1_product_0', '29.56'),
    ('study_calc1_integral_0', '2.667'),
    ('study_calc1_ftc_0', '6'),
    ('study_calc1_optimize_0', '4 m'),
    ('study_calc1_related_0', '12.57 m²/s'),
    ('study_calc2_substitution_0', '6.389'),
    ('study_calc2_parts_0', '8.389'),
    ('study_calc2_improper_0', '0.5'),
    ('study_calc2_geometric_0', '2'),
    ('study_calc2_taylor_0', '1.105'),
    ('study_calc2_disk_0', '8.378 units³'),
    ('study_calc2_polar_0', '3.142 units²'),
    ('study_calc2_partial_0', '0.2877'),
    ('study_calc3_partial_0', '4'),
    ('study_calc3_gradient_0', '4.472'),
    ('study_calc3_direction_0', '4'),
    ('study_calc3_double_0', '3'),
    ('study_calc3_triple_0', '12 kg'),
    ('study_calc3_divergence_0', '5'),
    ('study_calc3_curl_0', '4'),
    ('study_calc3_line_0', '5'),
    ('study_linear_det_0', '4'),
    ('study_linear_system_0', '2'),
    ('study_linear_eigen_0', '4'),
    ('study_linear_projection_0', '2'),
    ('study_ode_decay_0', '1.353'),
    ('study_ode_forcing_0', '3'),
    ('study_ode_ivp_0', '9'),
    ('study_ode_roots_0', '3'),
    ('study_physics1_velocity_0', '7 m/s'),
    ('study_physics1_projectile_0', '1 s'),
    ('study_physics1_newton_0', '4 m/s²'),
    ('study_physics1_energy_0', '6.264 m/s'),
    ('study_physics1_momentum_0', '3 m/s'),
    ('study_physics1_rotation_0', '9 J'),
    ('study_physics1_spring_0', '0.6283 s'),
    ('study_physics1_wave_0', '10 m/s'),
    ('study_physics2_coulomb_0', '0.03595 N'),
    ('study_physics2_field_0', '0.004 N'),
    ('study_physics2_potential_0', '2 J'),
    ('study_physics2_ohm_0', '4 A'),
    ('study_physics2_capacitor_0', '0.1 mJ'),
    ('study_physics2_magnetic_0', '0.8 N'),
    ('study_physics2_faraday_0', '0.4 V'),
    ('study_physics2_lens_0', '15 cm'),
])
def test_numeric_answers_against_independent_reference_values(identity, answer):
    card = next(card for card in build_bank() if card['id'] == identity)
    quiz = card['quiz']
    assert quiz['options'][quiz['correct_index']] == answer


def test_out_of_range_correct_answer_is_rejected():
    card = deepcopy(build_bank()[0])
    card['quiz']['correct_index'] = 7
    with pytest.raises(ValueError, match='outside'):
        validate_feed({'last_updated': '2026-10-25T00:00:00Z', 'calendar_mode': 'BASELINE',
                       'active_exam_course': None, 'cards': [card]})


def test_nhl_metadata_uses_publication_time_and_short_description():
    text = '<meta property="og:title" content="Team wins | Utah Mammoth"><meta name="description" content="A short game recap."><script>"datePublished":"2026-10-24T21:00:00Z","dateModified":"2026-10-25T01:00:00Z"</script>'
    entry = parse_article(text, 'https://www.nhl.com/utah/news/recap')
    card = normalize_entry(entry, {'name': 'nhl_mammoth', 'category': 'SPORTS', 'sport': 'hockey', 'team': 'Utah Mammoth'})
    assert card['title'] == 'Team wins'
    assert card['created_at'] == '2026-10-24T21:00:00Z'
    assert card['body_markdown'] == 'A short game recap.'
    assert card['team'] == 'Utah Mammoth'
    assert card['sport'] == 'hockey'
    escaped = text.replace('"datePublished":"', '\\"datePublished\\":\\"')
    assert parse_article(escaped, entry['link'])['published'] == '2026-10-24T21:00:00Z'


def test_team_feed_does_not_mislabel_league_wide_news():
    entry = {'title': 'A league-wide ranking', 'summary': 'All teams in the league', 'published': '2026-10-24T21:00:00Z'}
    source = {'name': 'espn_mammoth', 'category': 'SPORTS', 'sport': 'hockey', 'team': 'Utah Mammoth'}
    assert normalize_entry(entry, source) is None
    entry['title'] = 'Utah Mammoth game preview'
    assert normalize_entry(entry, source)['team'] == 'Utah Mammoth'
