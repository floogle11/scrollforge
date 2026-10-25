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
    assert len(cards) == 220
    assert sum(bool(card.get('quiz')) for card in cards) == 200
    assert len({card['id'] for card in cards}) == len(cards)
    assert len({card['body_markdown'] for card in cards}) == len(cards)
    counts = Counter(card['course_tag'] for card in cards)
    assert set(counts) == {'ME-3310', 'ENGR-2300', 'ME-3140', 'ME-3010', 'ME-2010'}
    assert min(counts.values()) >= 20
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
