"""Real-browser UI checks against a GitHub Pages-style subpath deployment."""
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CHROME = Path(os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "C:/Program Files/Google/Chrome/Application/chrome.exe"))


class _SubpathHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)

    def translate_path(self, path):
        path = urlsplit(path).path
        prefix = "/scrollforge/"
        if path.startswith(prefix):
            path = "/" + path[len(prefix):]
        return super().translate_path(path)

    def log_message(self, *_args):
        pass


@pytest.fixture(scope="module")
def site_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SubpathHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/scrollforge/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed")
    with sync_playwright() as playwright:
        executable = str(CHROME) if CHROME.is_file() else None
        try:
            instance = playwright.chromium.launch(headless=True, executable_path=executable)
        except Exception as exc:
            pytest.skip(f"No usable Chromium browser is installed: {exc}")
        yield instance
        instance.close()


def _fixture_feed():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    stamp = lambda days=0: (now - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    def card(card_id, category, title, days=0, source=None):
        return {"id": card_id, "created_at": stamp(days), "category": category,
                "course_tag": "ME-3310" if category.startswith("CHALLENGE") else None,
                "title": title, "body_markdown": "A useful field note with $Q=AV$.",
                "solution_markdown": "Balance first.\nThen **check units**." if category.startswith("CHALLENGE") else None,
                "source_url": source, "parent_card_id": None, "comments": []}
    cards = [card("challenge-one", "CHALLENGE_CURRENT", "Continuity gut check"),
             card("sports-fresh", "SPORTS", "Fresh Broncos headline", source="https://example.test/current-story"),
             card("story-fresh", "STORY", "A field story"),
             card("challenge-two", "CHALLENGE_PAST", "A second independent challenge"),
             card("engineering-note", "DEEP_CUT", "Evergreen engineering note"),
             card("news-old", "NEWS", "Old threaded headline", days=90),
             card("story-old", "STORY", "Expired story", days=40),
             card("duplicate-old", "SPORTS", "Duplicate stale version", days=1,
                  source="https://example.test/current-story?utm_source=duplicate")]
    cards[0]["body_markdown"] = "Safe <img src=x onerror=window.__xss=1> and [bad](javascript:window.__xss=2). What is $Q=AV$?"
    for target, suffix in [(cards[0], "one"), (cards[5], "old")]:
        target["comments"] = [{"id": "reply-" + suffix, "author": "CODEX", "body_markdown": "A useful reply.",
                               "created_at": stamp(), "unread": True, "issue_number": None}]
    return {"last_updated": stamp(), "calendar_mode": "BASELINE", "active_exam_course": None, "cards": cards}


def _page(browser, site_url, viewport=None, feed=None, service_workers="block"):
    context = browser.new_context(viewport=viewport or {"width": 390, "height": 844}, service_workers=service_workers)
    page = context.new_page()
    if feed is not None:
        page.route("**/data/feed.json", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(feed)))
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    page.goto(site_url, wait_until="domcontentloaded")
    page.locator(".feed-card").first.wait_for()
    return context, page


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["mobile", "desktop"])
def test_native_scrolling_keeps_multiple_cards_and_tracks_only_visible_cards(browser, site_url, viewport):
    context, page = _page(browser, site_url, viewport, _fixture_feed())
    try:
        assert page.locator(".feed-card").count() >= 5
        assert page.locator("#nextButton").count() == 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator('.feed-card[data-card-id="news-old"]').count() == 0
        assert page.locator('.feed-card[data-card-id="story-old"]').count() == 0
        assert page.locator('.feed-card[data-card-id="duplicate-old"]').count() == 0
        page.wait_for_timeout(150)
        last_id = page.locator(".feed-card").last.get_attribute("data-card-id")
        assert last_id not in page.evaluate("JSON.parse(localStorage.getItem('scrollforge.seen_card_ids') || '[]')")
        page.evaluate("window.__firstCard = document.querySelector('.feed-card')")
        page.mouse.wheel(0, 800)
        page.wait_for_function("scrollY > 400")
        assert page.evaluate("window.__firstCard === document.querySelector('.feed-card')")
        assert page.locator(".feed-card").count() >= 5
        page.locator(".feed-card").last.scroll_into_view_if_needed()
        page.wait_for_function("id => JSON.parse(localStorage.getItem('scrollforge.seen_card_ids') || '[]').includes(id)", arg=last_id)
        assert page.evaluate("window.__xss || 0") == 0
        assert page.locator("img").count() == 0
    finally:
        context.close()


def test_keyboard_moves_the_viewport_and_reveals_active_card(browser, site_url):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    try:
        page.keyboard.press("j")
        page.wait_for_function("document.querySelector('.feed-card[data-active]').dataset.cardIndex === '1'")
        assert page.evaluate("scrollY") > 100
        page.keyboard.press("k")
        page.wait_for_function("document.querySelector('.feed-card[data-active]').dataset.cardIndex === '0'")
        card = page.locator('[data-card-id="challenge-one"]').first
        card.evaluate("el => el.scrollIntoView({block:'start'})")
        page.wait_for_function("document.querySelector('.feed-card[data-active]').dataset.cardId === 'challenge-one'")
        page.keyboard.press("Space")
        assert card.locator(".solution-panel").evaluate("el => el.classList.contains('open')")
        assert not page.locator('[data-card-id="challenge-two"] .solution-panel').evaluate("el => el.classList.contains('open')")
        page.keyboard.press("c")
        assert card.locator("textarea").evaluate("el => document.activeElement === el")
    finally:
        context.close()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["mobile", "desktop"])
def test_comments_preserve_other_cards_drafts_and_scroll(browser, site_url, viewport):
    context, page = _page(browser, site_url, viewport, _fixture_feed())
    posts = []
    def issue(route):
        posts.append({"body": json.loads(route.request.post_data), "headers": route.request.headers})
        route.fulfill(status=201, content_type="application/json", body='{"number":42}')
    page.route("https://api.github.com/repos/owner/repo/issues", issue)
    try:
        page.evaluate("localStorage.setItem('scrollforge.repo_slug','owner/repo');localStorage.setItem('scrollforge.github_token','test-token')")
        other = page.locator('[data-card-id="challenge-two"]').first
        other.locator(".comment-toggle").click()
        other.locator("textarea").fill("Keep this other draft")
        other.locator(".comment-toggle").click()
        target = page.locator('[data-card-id="challenge-one"]').first
        target.locator(".comment-toggle").click()
        target.locator("textarea").fill("Can you show the units?")
        target.locator('.comment-form button[type="submit"]').scroll_into_view_if_needed()
        before = page.evaluate("scrollY")
        page.evaluate("window.__other = document.querySelector('[data-card-id=challenge-two]')")
        target.locator('.comment-form button[type="submit"]').click()
        target.get_by_text("QUEUED FOR LOCAL CODEX RUN", exact=False).wait_for()
        assert page.evaluate("scrollY") >= before - 100
        assert page.evaluate("window.__other === document.querySelector('[data-card-id=challenge-two]')")
        assert other.locator("textarea").input_value() == "Keep this other draft"
        assert len(posts) == 1
        assert posts[0]["body"]["labels"] == ["pending-codex"]
        assert json.loads(posts[0]["body"]["body"])["card_id"] == "challenge-one"
        assert posts[0]["headers"]["authorization"] == "Bearer test-token"
        assert target.locator(".pending-tag").count() == 1
    finally:
        context.close()


def test_inbox_opens_archived_thread_and_marks_reply_read(browser, site_url):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    try:
        assert page.locator("#inboxCount").inner_text() == "2"
        page.locator("#inboxButton").click()
        page.locator('.inbox-item[data-card-id="news-old"]').click()
        old = page.locator('[data-card-id="news-old"]').first
        old.wait_for()
        assert old.locator(".card-comments").evaluate("el => el.classList.contains('open')")
        assert page.locator("#inboxDrawer").get_attribute("aria-hidden") == "true"
        assert page.locator("#inboxCount").inner_text() == "1"
        assert "reply-old" in page.evaluate("JSON.parse(localStorage.getItem('scrollforge.read_comment_ids'))")
        assert page.evaluate("scrollY") > 100
    finally:
        context.close()


def test_review_recycles_engineering_only_and_never_clears_seen_headlines(browser, site_url):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    try:
        page.evaluate("localStorage.setItem('scrollforge.seen_card_ids', JSON.stringify(['sports-fresh','story-fresh']))")
        page.locator(".review-engineering").click()
        categories = page.locator(".feed-card .category-chip").all_inner_texts()
        assert categories
        assert all("CHALLENGE" in category.upper() or "ENGINEERING" in category.upper() for category in categories)
        assert "sports-fresh" in page.evaluate("JSON.parse(localStorage.getItem('scrollforge.seen_card_ids'))")
        assert page.locator('[data-card-id="sports-fresh"]').count() == 0
        page.reload(wait_until="domcontentloaded")
        page.locator(".feed-end").wait_for()
        assert page.locator('[data-card-id="sports-fresh"]').count() == 0
    finally:
        context.close()


def test_seen_headline_does_not_return_under_a_new_rss_id(browser, site_url):
    feed = _fixture_feed()
    context, page = _page(browser, site_url, feed=feed)
    try:
        headline = page.locator('.feed-card[data-card-id="sports-fresh"]')
        headline.scroll_into_view_if_needed()
        page.wait_for_function("JSON.parse(localStorage.getItem('scrollforge.seen_source_urls') || '[]').includes('https://example.test/current-story')")
        fresh = next(card for card in feed["cards"] if card["id"] == "sports-fresh")
        fresh["id"] = "sports-new-rss-id"
        fresh["source_url"] += "?utm_source=changed"
        page.reload(wait_until="domcontentloaded")
        page.locator(".feed-end").wait_for()
        assert page.locator('.feed-card[data-card-id="sports-new-rss-id"]').count() == 0
        assert page.locator('.feed-card[data-card-id="duplicate-old"]').count() == 0
    finally:
        context.close()


@pytest.mark.parametrize("mode", ["BASELINE", "EXAM_WINDOW", "CRUNCH_WINDOW", "EXAM_DAY"])
def test_mixer_keeps_challenges_uses_evergreen_spacers_and_never_repeats_news(browser, site_url, mode):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    try:
        result = page.evaluate("""mode => {
          const cards = Array.from({length:11}, (_, i) => ({id:'c'+i, category: i%2 ? 'CHALLENGE_CURRENT':'CHALLENGE_PAST'}));
          cards.push({id:'seen-news',category:'SPORTS'}, {id:'fresh-news',category:'NEWS'}, {id:'deep',category:'DEEP_CUT'});
          const output = ScrollForge.interleaveCards(cards,['seen-news','deep'],mode,[{category:'CHALLENGE_CURRENT'},{category:'CHALLENGE_PAST'}]);
          let run=2,maxRun=2;
          for(const card of output) {run=card.category.startsWith('CHALLENGE_') ? run+1:0;maxRun=Math.max(run,maxRun);}
          return {maxRun,ids:output.map(card=>card.id)};
        }""", mode)
        assert result["maxRun"] <= 2
        assert "seen-news" not in result["ids"]
        assert result["ids"].count("fresh-news") == 1
        assert all("c" + str(i) in result["ids"] for i in range(11))
    finally:
        context.close()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["mobile", "desktop"])
def test_seeded_scrolling_feed_screenshot(browser, site_url, viewport):
    context, page = _page(browser, site_url, viewport)
    try:
        assert page.locator(".feed-card").count() >= 2
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.evaluate("document.documentElement.scrollHeight > innerHeight")
        results = ROOT / "test-results"
        results.mkdir(exist_ok=True)
        page.screenshot(path=str(results / ("mobile.png" if viewport["width"] == 390 else "desktop.png")))
    finally:
        context.close()


def test_service_worker_serves_scrolling_feed_offline(browser, site_url):
    context, page = _page(browser, site_url, service_workers="allow")
    try:
        page.wait_for_function("!!navigator.serviceWorker.controller", timeout=15000)
        context.set_offline(True)
        page.reload(wait_until="domcontentloaded", timeout=15000)
        page.locator(".feed-card").first.wait_for()
        assert "OFFLINE" in page.locator("#networkText").inner_text()
        assert page.locator(".feed-card").count() >= 2
        page.mouse.wheel(0, 600)
        page.wait_for_function("scrollY > 100")
    finally:
        context.close()


def test_delayed_repository_default_preserves_typed_settings(browser, site_url):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    delayed = []
    page.route("**/data/repo.json", lambda route: delayed.append(route))
    try:
        page.locator("#settingsButton").click()
        page.locator("#repoSlug").fill("owner/custom-feed")
        page.wait_for_timeout(100)
        assert delayed
        for route in delayed:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"repository":"floogle11/scrollforge"}))
        page.wait_for_timeout(100)
        assert page.locator("#repoSlug").input_value() == "owner/custom-feed"
        page.locator("#repoToken").fill("test-token")
        page.locator('#settingsForm button[type="submit"]').click()
        assert page.evaluate("localStorage.getItem('scrollforge.repo_slug')") == "owner/custom-feed"
        page.keyboard.press("Escape")
        assert not page.locator("#settingsModal").is_visible()
    finally:
        context.close()


def test_reply_poll_updates_inbox_without_replacing_cards_or_drafts(browser, site_url):
    import copy
    feed = _fixture_feed()
    context, page = _page(browser, site_url, feed=feed)
    delayed = []
    try:
        target = page.locator('.feed-card[data-card-id="challenge-one"]').first
        target.locator(".solution-toggle").click()
        draft = page.locator('.feed-card[data-card-id="challenge-two"]').first
        draft.locator(".comment-toggle").click()
        draft.locator("textarea").fill("Keep my draft while an answer arrives")
        page.evaluate("window.__existingCard = document.querySelector('[data-card-id=challenge-two]')")
        before_order = page.locator(".feed-card").evaluate_all("cards => cards.map(card => card.dataset.cardId)")
        before_scroll = page.evaluate("scrollY")
        next_feed = copy.deepcopy(feed)
        answer = {"id": "poll-reply", "author": "CODEX", "body_markdown": "New terminal answer <img src=x onerror=window.__pollXss=1>",
                  "created_at": feed["last_updated"], "unread": True, "issue_number": 123}
        next_feed["cards"][0]["comments"].append(answer)
        new_card = copy.deepcopy(next_feed["cards"][1])
        new_card.update(id="poll-new-card", title="Another fresh headline", source_url="https://example.test/new-headline")
        next_feed["cards"].append(new_card)
        page.route("**/data/feed.json", lambda route: delayed.append(route))
        page.evaluate("window.__pollResult = ScrollForge.refreshReplies(); true")
        page.wait_for_timeout(100)
        assert len(delayed) == 1
        assert page.evaluate("async () => await ScrollForge.refreshReplies()") is False
        assert len(delayed) == 1
        delayed[0].fulfill(status=200, content_type="application/json", body=json.dumps(next_feed))
        assert page.evaluate("async () => await window.__pollResult") is True
        assert page.locator("#inboxCount").inner_text() == "3"
        assert "New terminal answer" in target.locator(".comment-list").text_content()
        assert target.locator(".solution-panel").evaluate("el => el.classList.contains('open')")
        assert draft.locator("textarea").input_value() == "Keep my draft while an answer arrives"
        assert page.evaluate("window.__existingCard === document.querySelector('[data-card-id=challenge-two]')")
        assert page.locator(".feed-card").evaluate_all("cards => cards.map(card => card.dataset.cardId)") == before_order
        assert abs(page.evaluate("scrollY") - before_scroll) < 3
        assert page.locator("#newSignalsButton").is_visible()
        assert page.locator("#newSignalsButton").inner_text() == "1 NEW SIGNAL - REFRESH"
        assert page.locator('.feed-card[data-card-id="poll-new-card"]').count() == 0
        assert page.evaluate("window.__pollXss || 0") == 0
        context.set_offline(True)
        assert page.evaluate("async () => await ScrollForge.refreshReplies()") is False
    finally:
        context.close()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["mobile", "desktop"])
def test_topics_search_and_sort_preserve_post_state(browser, site_url, viewport):
    feed = _fixture_feed()
    # Include fresh general news independently from NFL and old archived news.
    import copy
    headline = copy.deepcopy(feed["cards"][1])
    headline.update(id="fresh-news", category="NEWS", title="A new world headline",
                    source_url="https://example.test/world-news")
    feed["cards"].append(headline)
    context, page = _page(browser, site_url, viewport, feed)
    try:
        card = page.locator('.feed-card[data-card-id="challenge-one"]')
        card.locator(".solution-toggle").click()
        card.locator(".comment-toggle").click()
        card.locator("textarea").fill("Keep this draft across topic changes")
        page.evaluate("window.__draftCard = document.querySelector('[data-card-id=challenge-one]')")
        page.locator('.topic-tabs [data-topic="news"]').click()
        assert page.locator(".feed-card:visible").count() == 1
        assert page.locator(".feed-card:visible").get_attribute("data-card-id") == "fresh-news"
        page.locator('.topic-tabs [data-topic="sports"]').click()
        assert page.locator(".feed-card:visible").count() == 1
        assert page.locator(".feed-card:visible").get_attribute("data-card-id") == "sports-fresh"
        page.locator('.topic-tabs [data-topic="all"]').click()
        page.locator("#feedSearch").fill("Continuity")
        assert page.locator(".feed-card:visible").count() == 1
        assert card.is_visible()
        page.locator("#feedSearch").fill("no posts match this text")
        assert page.locator(".feed-card:visible").count() == 0
        assert page.locator("#filterEmpty").is_visible()
        page.locator("#feedSearch").fill("")
        page.locator("#feedSort").select_option("new")
        stamps = page.locator(".feed-card:visible time").evaluate_all("nodes => nodes.map(node => Date.parse(node.dateTime))")
        assert stamps == sorted(stamps, reverse=True)
        assert card.locator("textarea").input_value() == "Keep this draft across topic changes"
        assert card.locator(".solution-panel").is_visible()
        assert page.evaluate("window.__draftCard === document.querySelector('[data-card-id=challenge-one]')")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()
