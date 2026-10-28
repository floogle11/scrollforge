import copy
import json

import chess
import pytest

from worker.chess_content import build_bank, prepare_chess
from worker.generate_batch import validate_output
from worker.interests import load_interests, validate_interests


def test_chess_bank_contract_and_tactical_objectives():
    cards = build_bank()
    validate_output({"new_cards": cards, "comment_replies": []})
    by_id = {c['id'].removeprefix('chess_italian_'): c for c in cards}
    fork = chess.Board(by_id['fork']['chess']['fen'])
    fork.push_san('Nxf7')
    assert chess.D8 in fork.attacks(chess.F7) and chess.H8 in fork.attacks(chess.F7)
    assert not fork.is_check()
    assert fork.is_legal(chess.Move.from_uci('e8f7'))
    central = chess.Board(by_id['central_break']['chess']['fen'])
    central.push_san('d4')
    assert chess.C5 in central.attacks(chess.D4) and chess.E5 in central.attacks(chess.D4)
    for card in cards:
        assert '<svg' in card['chess']['svg']
        if card['quiz']:
            assert card['quiz']['options'][card['quiz']['correct_index']] == card['chess']['line'][0]


def test_illegal_or_false_check_lines_rejected_and_svg_rebuilt():
    card = build_bank()[0]
    for line in [['e4'], ['Bc5#']]:
        broken = copy.deepcopy(card)
        broken['chess']['line'] = line
        with pytest.raises(ValueError):
            prepare_chess(broken)
    card['chess']['svg'] = '<script>bad()</script>'
    prepare_chess(card)
    assert '<script' not in card['chess']['svg']


def test_empty_interests_override_defaults_and_untrusted_issue_ignored(monkeypatch):
    import requests
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return [dict(title='ScrollForge current interests', user={'login':'stranger'},
                         body=json.dumps({'kind':'scrollforge-interests-v1','interests':['bad']})),
                    dict(title='ScrollForge current interests', user={'login':'owner'},
                         body=json.dumps({'kind':'scrollforge-interests-v1','interests':[]}))]
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: Response())
    assert load_interests('owner/repo', 'test') == []
    assert validate_interests([' Chess ', 'chess']) == ['Chess']
    with pytest.raises(ValueError): validate_interests(['a'] * 13)


def test_generation_reserves_existing_budget_and_passes_interests(monkeypatch):
    from worker import generate_batch, interests
    captured = []
    monkeypatch.setattr(interests, 'load_interests', lambda *args: ['Italian Game'])
    monkeypatch.setattr(generate_batch, 'call_model', lambda **kw: captured.append(kw) or {'new_cards':[], 'comment_replies':[]})
    generate_batch.generate_batch(issues=[], counts_override={'current_coursework':14, 'past_coursework':6})
    assert captured[0]['counts'] == {'current_coursework':14, 'past_coursework':0, 'interests':6}
    assert captured[0]['interests'] == ['Italian Game']
    generate_batch.generate_batch(issues=[], generate_new_cards=False)
    assert captured[1]['interests'] == []
    assert sum(captured[1]['counts'].values()) == 0


def test_generated_interest_retention_preserves_lessons_and_threads():
    from worker.retention import retain_cards
    card = build_bank()[0]
    cards = [dict(card, id=f'generated_{i}', created_at=f'2026-10-28T12:{i:02d}:00Z') for i in range(60)]
    cards[0]['comments'] = [{'id':'thread'}]
    cards.append(card)
    kept = retain_cards(cards, protected_ids={'generated_1'})
    assert len(kept) == 57  # 54 recent, one conversation, one protected parent, one starter.
    assert {'generated_0', 'generated_1', card['id']} <= {c['id'] for c in kept}
