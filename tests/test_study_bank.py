from collections import Counter
from copy import deepcopy
import math
import re
import pytest

from worker.study_bank import build_bank
from worker.run_pipeline import validate_feed
from worker.ingest_nhl import parse_article
from worker.ingest_rss import normalize_entry


def test_bank_is_diverse_reproducible_and_contract_valid():
    cards = build_bank()
    assert cards == build_bank()
    assert len(cards) == 472
    assert sum(bool(card.get('quiz')) for card in cards) == 452
    assert len({card['id'] for card in cards}) == len(cards)
    assert len({card['body_markdown'] for card in cards}) == len(cards)
    counts = Counter(card['course_tag'] for card in cards)
    assert set(counts) == {'ME-3310', 'ENGR-2300', 'ME-3140', 'ME-3010', 'ME-2010', 'CALC-I', 'CALC-II', 'CALC-III', 'LINEAR-ALG', 'DIFF-EQ', 'PHYS-I', 'PHYS-II'}
    assert min(counts.values()) >= 16
    for course in ['CALC-I', 'CALC-II', 'CALC-III', 'PHYS-I', 'PHYS-II']:
        assert counts[course] == 37
    validate_feed({'last_updated': '2026-10-25T00:00:00Z', 'calendar_mode': 'BASELINE',
                   'active_exam_course': None, 'cards': cards})
    for card in cards:
        if card['diagram'] == 'plot':
            assert card['diagram_data']['lower'] < card['diagram_data']['upper']
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
    actual = quiz['options'][quiz['correct_index']]
    assert math_value(actual) == pytest.approx(float(answer.split()[0]), rel=0.0005)
    if actual.startswith('$'):
        assert actual.split('$')[-1].strip() == ' '.join(answer.split()[1:])
    else:
        assert actual == answer


def math_value(option):
    """Evaluate the bank's small numeric TeX subset, only in these tests.

    Independent rounded reference values above remain unchanged. This parser
    lets them check exact expressions as well as the old decimal answers.
    """
    if not option.startswith('$'):
        return float(option.split()[0])
    expression = option.split('$')[1]
    expression = expression.replace(r'\left', '').replace(r'\right', '').replace(r'\,', '')
    expression = expression.replace(r'\pi', 'pi').replace(r'\ln', 'log').replace(r'\infty', 'inf')
    previous = None
    while previous != expression:
        previous = expression
        expression = re.sub(r'\\sqrt\{([^{}]+)\}', r'sqrt(\1)', expression)
        expression = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'((\1)/(\2))', expression)
        expression = re.sub(r'\^\{([^{}]+)\}', r'**(\1)', expression)
    expression = re.sub(r'\^(\d+)', r'**\1', expression)
    expression = re.sub(r'(?<=[0-9)])(?=pi|e|sqrt|log|\()', '*', expression)
    # Input is repository-authored test data, never a feed/user expression.
    return float(eval(expression, {'__builtins__': {}}, dict(pi=math.pi, e=math.e, sqrt=math.sqrt, log=math.log, inf=math.inf)))


def test_exact_choices_have_no_equivalent_numeric_distractors():
    from worker.review_choices import choices
    seen = []
    def check(key, course, title, body, value, unit, *unused):
        options, exact = choices(key, value, unit)
        values = [math_value(option) for option in options]
        assert values[0] == pytest.approx(value, rel=0.0005), key
        for i, left in enumerate(values):
            assert not any(math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-10) for right in values[i+1:]), (key, options)
        seen.append(key)
    # Re-run every numerical template with its original formula, independently
    # of the choice recipes. Includes every variant, not only v=0.
    import worker.study_bank as bank
    from unittest.mock import patch
    def audited_choices(key, value, unit):
        check(key, None, None, None, value, unit)
        return choices(key, value, unit)
    with patch.object(bank, 'choices', audited_choices):
        bank.build_bank()
    assert len(seen) == 368


def test_exponential_integrals_use_exact_answers_and_boundary_errors():
    cards = {card['id']: card for card in build_bank()}
    assert set(cards['study_calc2_parts_0']['quiz']['options']) == {'$e^{2}+1$', '$e^{2}-1$', '$2e^{2}$', '$3e^{2}-1$'}
    assert '$e^{2}-1$' in cards['study_calc2_substitution_0']['quiz']['options']
    assert 'closest' not in cards['study_calc2_parts_0']['body_markdown']
    for key in ('calc1_product', 'calc1_related', 'calc2_parts', 'calc2_partial', 'calc2_disk', 'calc2_polar', 'ode_decay', 'physics1_energy', 'physics1_spring'):
        for v in range(4):
            options = cards[f'study_{key}_{v}']['quiz']['options']
            assert all(option.startswith('$') for option in options)


def test_diagrams_match_setups_and_plots_have_actual_bounds():
    cards = {card['id']: card for card in build_bank()}
    expected = {'natural_frequency_0':'spring_undamped', 'physics1_spring_0':'spring_undamped',
                'damper_force_0':'damper', 'hydrostatic_0':'open_tank', 'ideal_gas_du_0':'sealed_tank',
                'physics1_momentum_0':'collision', 'physics2_faraday_0':'coil', 'newton_0':None,
                'roller_reaction':None, 'calc1_product_0':None, 'linear_system_0':None}
    for key, diagram in expected.items():
        assert cards['study_'+key]['diagram'] == diagram
    for v in range(4):
        data = cards[f'study_calc2_parts_{v}']['diagram_data']
        assert (data['function'],data['lower'],data['upper']) == ('parts',0,v+2)
    added = [c for c in cards.values() if c['id'].startswith('study_extra_')]
    assert len(added) == 60
    assert set(Counter(c['course_tag'] for c in added).values()) == {5}


def test_out_of_range_correct_answer_is_rejected():
    card = deepcopy(build_bank()[0])
    card['quiz']['correct_index'] = 7
    with pytest.raises(ValueError, match='outside'):
        validate_feed({'last_updated': '2026-10-25T00:00:00Z', 'calendar_mode': 'BASELINE',
                       'active_exam_course': None, 'cards': [card]})


def test_generated_challenges_can_omit_a_misleading_illustration():
    from worker.generate_batch import validate_output
    card = next(card for card in build_bank() if card['id']=='study_extra_log_parts')
    card.pop('topic')
    card.pop('diagram_labels')
    assert card['diagram'] is None
    validate_output({'comment_replies':[], 'new_cards':[card]})
    card['quiz'] = None
    with pytest.raises(ValueError, match='must include a quiz'):
        validate_output({'comment_replies':[], 'new_cards':[card]})


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
