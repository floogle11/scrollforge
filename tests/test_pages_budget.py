import json
from pathlib import Path

import pytest

from scripts.check_pages_budget import check_budget
from worker.run_pipeline import atomic_write


def _feed():
    return {'last_updated': '2026-10-25T00:00:00Z', 'calendar_mode': 'BASELINE',
            'active_exam_course': None, 'cards': []}


def test_published_site_is_within_budgets_and_marker_matches():
    assert check_budget()['errors'] == []


def test_atomic_feed_write_updates_tiny_marker(tmp_path):
    path = tmp_path / 'data/feed.json'
    atomic_write(path, _feed())
    assert json.loads(path.with_name('feed-meta.json').read_text()) == {
        'last_updated': _feed()['last_updated'], 'bytes': len(path.read_bytes())}
    assert check_budget(tmp_path)['errors'] == []
    path.with_name('feed-meta.json').write_text('{}')
    assert any('must match' in error for error in check_budget(tmp_path)['errors'])


def test_oversize_publication_keeps_original_feed_and_marker(tmp_path):
    path = tmp_path / 'feed.json'
    atomic_write(path, _feed())
    before = path.read_bytes(), path.with_name('feed-meta.json').read_bytes()
    large = _feed()
    large['cards'] = [
        {'id':f'p{i}', 'created_at':large['last_updated'], 'category':'DEEP_CUT', 'course_tag':None,
         'title':'Long conversation', 'body_markdown':'x'*4000, 'solution_markdown':None,
         'source_url':None, 'parent_card_id':None, 'comments':[]} for i in range(1400)]
    with pytest.raises(ValueError, match='5 MiB'):
        atomic_write(path, large)
    assert before == (path.read_bytes(), path.with_name('feed-meta.json').read_bytes())


def test_site_budget_catches_large_assets(tmp_path):
    atomic_write(tmp_path / 'data/feed.json', _feed())
    (tmp_path / 'oversized.bin').write_bytes(b'x'*(6*1024*1024))
    assert any('per-file budget' in error for error in check_budget(tmp_path)['errors'])
