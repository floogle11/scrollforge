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


def test_short_last_post_can_align_below_sticky_header(browser, site_url):
    context, page = _page(browser, site_url, {'width': 390, 'height': 1200}, _fixture_feed())
    try:
        for card in page.locator('.feed-card').all():
            identity = card.get_attribute('data-card-id')
            card.evaluate("node => node.scrollIntoView({block:'start'})")
            page.wait_for_function("id => document.querySelector('.feed-card[data-active]').dataset.cardId === id", arg=identity)
            assert card.evaluate('node => node.getBoundingClientRect().top') >= 100
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


def test_mixer_spaces_topics_and_learns_recurring_interests(browser, site_url):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    try:
        result = page.evaluate("""() => {
          const sf = ScrollForge, now = Date.now();
          const nasa = {id:'nasa',category:'NEWS',title:'NASA telescope explores Mars',source_url:'https://nasa.gov/one'};
          const moreSpace = {...nasa,id:'other',title:'An astronaut enters orbit',source_url:'https://another.test/two'};
          const politics = {...nasa,id:'politics',title:'Congress debates an election',source_url:'https://other.test/politics'};
          const votes = Object.fromEntries([0,1,2,3,4].map(i => ['v'+i,{value:1,at:now,features:sf.interestFeatures(nasa)}]));
          const profile = sf.preferenceProfile(votes,now);
          const faded = sf.preferenceProfile(votes,now+180*86400000);
          const negative = sf.preferenceProfile({n:{value:-1,at:now,features:sf.interestFeatures(nasa)}},now);
          const cards = Array.from({length:120},(_,i)=>({id:'p'+i,category:['NEWS','SPORTS','STORY'][i%3],title:'Post '+i,source_url:'https://source'+(i%5)+'.test/p'+i}));
          const outputs = Array.from({length:8},()=>sf.interleaveCards(cards));
          return {
            recurring: sf.preferenceWeight(moreSpace,profile)>sf.preferenceWeight(politics,profile),
            fades: sf.preferenceWeight(moreSpace,profile)>sf.preferenceWeight(moreSpace,faded),
            negative: sf.preferenceWeight(moreSpace,negative)<1,
            exploration: sf.preferenceWeight(moreSpace,negative)>0,
            varied: new Set(outputs.map(a=>a.slice(0,10).map(c=>c.id).join(','))).size,
            adjacent:outputs.some(out=>out.some((c,i)=>i<50 && i>0 && c.category===out[i-1].category)),
            unique:outputs.every(out=>new Set(out.map(c=>c.id)).size===cards.length && out.length===cards.length)
          };
        }""")
        assert result == {"recurring": True, "fades": True, "negative": True, "exploration": True,
                          "varied": 8, "adjacent": False, "unique": True}
    finally:
        context.close()


@pytest.mark.parametrize('viewport', [{'width':390,'height':844}, {'width':1440,'height':1000}])
def test_preferences_are_reversible_local_and_preserve_mounted_posts(browser, site_url, viewport):
    feed = _fixture_feed()
    # Enough unseen content for preference updates to re-rank later pages.
    feed['cards'] += [{**feed['cards'][1], 'id':f'extra-{i}', 'source_url':f'https://example.test/{i}'} for i in range(80)]
    context, page = _page(browser, site_url, viewport=viewport, feed=feed)
    try:
        node = page.locator('.feed-card').first
        card_id = node.get_attribute('data-card-id')
        node.evaluate('(node) => { window.__kept = node; }')
        node.locator('.comment-toggle').click()
        node.locator('textarea').fill('Keep this draft')
        before = page.evaluate('scrollY')
        node.locator('[data-preference="1"]').click()
        assert node.locator('[data-preference="1"]').get_attribute('aria-pressed') == 'true'
        assert page.evaluate('window.__kept.isConnected')
        assert node.locator('textarea').input_value() == 'Keep this draft'
        assert abs(page.evaluate('scrollY')-before) < 10
        assert len(page.evaluate("JSON.parse(localStorage.getItem('scrollforge.preferences.v1'))")) == 1
        node.locator('[data-preference="-1"]').click()
        assert node.locator('[data-preference="1"]').get_attribute('aria-pressed') == 'false'
        assert node.locator('[data-preference="-1"]').get_attribute('aria-pressed') == 'true'
        node.locator('[data-preference="-1"]').click()
        assert page.evaluate("JSON.parse(localStorage.getItem('scrollforge.preferences.v1'))") == {}
        node.locator('[data-preference="1"]').click()
        page.reload(wait_until='domcontentloaded')
        page.locator('.feed-card').first.wait_for()
        assert card_id in page.evaluate("JSON.parse(localStorage.getItem('scrollforge.preferences.v1'))")
        page.locator('#settingsButton').click()
        assert page.locator('#preferenceSummary').inner_text().startswith('More ')
        page.locator('#resetPreferences').click()
        assert page.evaluate("JSON.parse(localStorage.getItem('scrollforge.preferences.v1'))") == {}
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


def test_unchanged_version_marker_avoids_full_archive_poll(browser, site_url):
    feed = _fixture_feed()
    context, page = _page(browser, site_url, feed=feed)
    try:
        page.route('**/data/feed-meta.json', lambda route: route.fulfill(json={'last_updated':feed['last_updated']}))
        requests = []
        page.on('request', lambda request: requests.append(request.url))
        assert page.evaluate('async () => await ScrollForge.refreshReplies()')
        assert any(url.endswith('/feed-meta.json') for url in requests)
        assert not any(url.endswith('/feed.json') for url in requests)
    finally:
        context.close()


def test_foundation_subjects_render_diagrams_quizzes_and_filter(browser, site_url):
    from worker.study_bank import build_bank
    courses = ['CALC-I','CALC-II','CALC-III','LINEAR-ALG','DIFF-EQ','PHYS-I','PHYS-II']
    feed = _fixture_feed()
    feed['cards'] = [card for card in build_bank() if card['course_tag'] in courses]
    context, page = _page(browser, site_url, feed=feed)
    try:
        page.locator('.topic-tabs [data-topic="engineering"]').click()
        for course in courses:
            page.locator('#studyCourse').select_option(course)
            nodes = page.locator('.feed-card:visible')
            assert nodes.count() >= 16
            assert all(label == course for label in nodes.locator('.card-course').all_text_contents())
            # Illustrations are optional: do not force unrelated artwork onto
            # symbolic algebra, vector calculus or conceptual questions.
            assert nodes.locator('.study-visual svg').count() <= nodes.count()
            assert nodes.locator('.quiz').count() == nodes.count()
        page.locator('.feed-card:visible').first.locator('[data-answer]').first.click()
        assert 'worked answer' in page.locator('.feed-card:visible').first.locator('.quiz-feedback').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize('viewport', [{'width':390,'height':844}, {'width':1440,'height':1000}])
def test_review_figures_are_renderable_labeled_and_fit_the_canvas(browser, site_url, viewport):
    from worker.study_bank import build_bank
    cards = [c for c in build_bank() if c.get('diagram')]
    context, page = _page(browser, site_url, viewport=viewport, feed=_fixture_feed())
    try:
        result = page.evaluate('''cards => {
          const host=document.createElement('div'); document.body.append(host);
          const failures=[];
          for (const card of cards) {
            host.innerHTML=ScrollForgeDiagrams.render(card);
            const svg=host.querySelector('svg');
            if (!svg || !svg.getAttribute('aria-label')) {failures.push(card.id+': missing figure');continue;}
            for (const text of svg.querySelectorAll('text')) {
              const b=text.getBBox();
              if (b.x < 0 || b.y < 0 || b.x+b.width > 480 || b.y+b.height > 240) failures.push(card.id+': clipped '+text.textContent);
            }
          }
          host.remove(); return failures;
        }''', cards)
        assert result == []
        assert page.evaluate("ScrollForgeDiagrams.render({diagram:'tangent'})") == ''
        assert page.evaluate("ScrollForgeDiagrams.render({diagram:'plot',diagram_data:{}})") == ''
        # The integration-by-parts plot must start at y=0, curve upward and end
        # at x=2. This catches decorative curves or incorrect area endpoints.
        plot = next(c for c in cards if c['id']=='study_calc2_parts_0')
        page.evaluate("card => document.querySelector('.card-body').insertAdjacentHTML('afterend', ScrollForgeDiagrams.render(card))", plot)
        curve = page.locator('.diagram-curve').get_attribute('d')
        assert curve.startswith('M60.000 185.000')
        assert curve.endswith('L405.000 60.000')
        assert 'from 0 to 2' in page.locator('[data-diagram="plot"] svg').get_attribute('aria-label')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


def test_saved_answer_resets_when_question_or_correct_answer_changes(browser, site_url):
    from worker.study_bank import build_bank
    feed = _fixture_feed()
    question = next(c for c in build_bank() if c['id']=='study_calc2_parts_0')
    feed['cards'] = [question]
    context, page = _page(browser, site_url, feed=feed)
    try:
        page.locator('[data-answer]').first.click()
        assert page.locator('.quiz-option:disabled').count() == 4
        question['quiz']['correct_index'] = (question['quiz']['correct_index']+1)%4
        page.reload()
        page.locator('.review-engineering').click()
        page.locator('.quiz-option:not(:disabled)').first.wait_for()
        assert page.locator('.quiz-option:not(:disabled)').count() == 4
        page.locator('[data-answer]').first.click()
        question['body_markdown'] += ' Use exact form.'
        page.reload()
        page.locator('.review-engineering').click()
        page.locator('.quiz-option:not(:disabled)').first.wait_for()
        assert page.locator('.quiz-option:not(:disabled)').count() == 4
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


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["mobile", "desktop"])
def test_illustrated_quiz_feedback_retry_and_saved_answer(browser, site_url, viewport):
    feed = _fixture_feed()
    question = feed['cards'][0]
    question['quiz'] = {'options': ['1 m/s', '2 m/s', '3 m/s', '4 m/s', '5 m/s', '6 m/s'], 'correct_index': 4}
    question['diagram'] = 'pipe'
    question['diagram_labels'] = ['Q = 0.01 m³/s', 'D = 0.05 m']
    context, page = _page(browser, site_url, viewport, feed)
    try:
        card = page.locator('[data-card-id="challenge-one"]').first
        assert card.locator('.study-visual svg').is_visible()
        assert card.locator('.quiz-option').count() == 6
        assert not card.locator('.solution-panel').is_visible()
        card.locator('[data-answer="0"]').click()
        assert 'Not quite' in card.locator('.quiz-feedback').inner_text()
        assert card.locator('[data-answer="4"]').evaluate("el => el.classList.contains('correct')")
        assert card.locator('.solution-panel').is_visible()
        card.locator('.quiz-retry').click()
        assert not card.locator('.solution-panel').is_visible()
        card.locator('[data-answer="4"]').click()
        assert 'Correct.' in card.locator('.quiz-feedback').inner_text()
        page.locator('.topic-tabs [data-topic="sports"]').click()
        page.locator('.topic-tabs [data-topic="engineering"]').click()
        assert 'Correct.' in card.locator('.quiz-feedback').inner_text()
        page.reload(wait_until='domcontentloaded')
        # Read questions are intentionally absent from the fresh feed; reopen
        # the review bank rather than racing the read-tracking observer.
        page.locator('.review-engineering').click()
        card.locator('.quiz-feedback').wait_for()
        assert 'Correct.' in card.locator('.quiz-feedback').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        card.evaluate("node => node.scrollIntoView({block:'start'})")
        page.screenshot(path=str(ROOT / 'test-results' / ('quiz-mobile.png' if viewport['width'] == 390 else 'quiz-desktop.png')))
    finally:
        context.close()


def test_infinite_scroll_appends_without_recreating_posts_and_searches_unloaded_items(browser, site_url):
    import copy
    feed = _fixture_feed()
    base = copy.deepcopy(feed['cards'][1])
    feed['cards'] = []
    for index in range(85):
        post = copy.deepcopy(base)
        post.update(id=f'headline-{index}', title=f'A distinct headline {index}',
                    source_url=f'https://example.test/article-{index}')
        feed['cards'].append(post)
    context, page = _page(browser, site_url, feed=feed)
    try:
        assert page.locator('.feed-card').count() == 24
        initial = page.locator('.feed-card').evaluate_all('nodes => nodes.map(node => node.dataset.cardId)')
        page.evaluate("window.__firstPost = document.querySelector('.feed-card')")
        page.locator('.feed-card').last.scroll_into_view_if_needed()
        page.wait_for_function("document.querySelectorAll('.feed-card').length > 24")
        assert page.evaluate("window.__firstPost === document.querySelector('.feed-card')")
        assert page.locator('.feed-card').evaluate_all('nodes => nodes.slice(0,24).map(node => node.dataset.cardId)') == initial
        ids = page.locator('.feed-card').evaluate_all('nodes => nodes.map(node => node.dataset.cardId)')
        assert len(ids) == len(set(ids))
        missing = next(f'headline-{index}' for index in range(85) if f'headline-{index}' not in ids)
        page.locator('#feedSearch').fill('A distinct headline ' + missing.split('-')[1])
        assert page.locator(f'[data-card-id="{missing}"]').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


def test_hockey_team_filters_and_official_reddit_preview(browser, site_url):
    import copy
    feed = _fixture_feed()
    mammoth = copy.deepcopy(feed['cards'][1])
    mammoth.update(id='mammoth-post', sport='hockey', team='Utah Mammoth', title='Mammoth game discussion',
                   source_url='https://www.reddit.com/r/Utah_Hockey/comments/abc123/game_discussion/')
    avalanche = copy.deepcopy(mammoth)
    avalanche.update(id='avalanche-post', team='Colorado Avalanche', title='Avalanche preview',
                     source_url='https://example.test/avalanche')
    feed['cards'] += [mammoth, avalanche]
    context, page = _page(browser, site_url, feed=feed)
    page.route('https://embed.reddit.com/**', lambda route: route.fulfill(status=200, content_type='text/html', body='<p>Original Reddit post</p>'))
    try:
        page.locator('.topic-tabs [data-topic="hockey"]').click()
        assert page.locator('.feed-card:visible').count() == 2
        page.locator('.team-picks [data-topic="mammoth"]').click()
        assert page.locator('.feed-card:visible').count() == 1
        card = page.locator('[data-card-id="mammoth-post"]')
        card.locator('.reddit-toggle').click()
        frame = card.locator('iframe')
        assert frame.get_attribute('src').startswith('https://embed.reddit.com/r/Utah_Hockey/comments/abc123/')
        assert frame.get_attribute('sandbox') == 'allow-scripts allow-same-origin allow-popups'
        assert frame.get_attribute('title') == 'Original Reddit post'
        card.locator('.reddit-toggle').click()
        assert not frame.is_visible()
        page.locator('.team-picks [data-topic="avalanche"]').click()
        assert page.locator('.feed-card:visible').get_attribute('data-card-id') == 'avalanche-post'
    finally:
        context.close()


def test_current_interests_sync_empty_removal_and_chess_board(browser, site_url):
    from worker.chess_content import build_bank
    feed = _fixture_feed()
    feed['cards'].extend(build_bank())
    context, page = _page(browser, site_url, feed=feed)
    saved = []
    def github(route):
        if route.request.method == 'GET':
            route.fulfill(content_type='application/json', body='[]')
        else:
            saved.append(route.request.post_data_json)
            route.fulfill(status=201, content_type='application/json', body=json.dumps({'number':42,'user':{'login':'owner'}}))
    page.route('https://api.github.com/**', github)
    page.evaluate("localStorage.setItem('scrollforge.repo_slug', 'owner/repo'); localStorage.setItem('scrollforge.github_token', 'test-token')")
    page.locator('#settingsButton').click()
    from playwright.sync_api import expect
    expect(page.locator('#currentInterests')).to_be_enabled()
    assert 'Italian Game' in page.locator('#currentInterests').input_value()
    page.locator('#currentInterests').fill('')
    page.locator('#saveInterests').click()
    expect(page.locator('#interestsFeedback')).to_contain_text('paused')
    assert json.loads(saved[0]['body'])['interests'] == []
    page.locator('#settingsModal [data-close-panel]').click()
    page.locator('.topic-tabs [data-topic="chess"]').click()
    expect(page.locator('.chess-board').first).to_be_visible()
    assert page.locator('.chess-board img').first.evaluate('(img) => img.complete && img.naturalWidth > 0')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.evaluate("localStorage.setItem('scrollforge.seen_card_ids', JSON.stringify(" + json.dumps([c['id'] for c in feed['cards']]) + "))")
    page.reload(wait_until='domcontentloaded')
    page.locator('.topic-tabs [data-topic="chess"]').click()
    expect(page.locator('.chess-board').first).to_be_visible()
    context.close()


def test_existing_interests_update_and_failed_save_preserves_draft(browser, site_url):
    context, page = _page(browser, site_url, feed=_fixture_feed())
    stored = {'kind':'scrollforge-interests-v1', 'interests':['Italian Game', 'Astronomy']}
    writes = []
    fail = [False]
    def github(route):
        if route.request.method == 'GET':
            route.fulfill(content_type='application/json', body=json.dumps([
                {'number':9, 'title':'ScrollForge current interests', 'body':json.dumps(stored)}]))
        else:
            writes.append((route.request.method, route.request.url, route.request.post_data_json))
            if fail[0]:
                route.fulfill(status=403, content_type='application/json', body='{}')
            else:
                stored.update(json.loads(route.request.post_data_json['body']))
                route.fulfill(content_type='application/json', body=json.dumps({'number':9, 'user':{'login':'owner'}}))
    page.route('https://api.github.com/**', github)
    page.evaluate("localStorage.setItem('scrollforge.repo_slug', 'owner/repo'); localStorage.setItem('scrollforge.github_token', 'test-token')")
    page.locator('#settingsButton').click()
    from playwright.sync_api import expect
    expect(page.locator('#currentInterests')).to_be_enabled()
    assert page.locator('#currentInterests').input_value() == 'Italian Game\nAstronomy'
    page.locator('#currentInterests').fill('Italian Game\nHistory')
    page.locator('#saveInterests').click()
    expect(page.locator('#interestsFeedback')).to_contain_text('Saved for')
    assert writes[0][0] == 'PATCH' and writes[0][1].endswith('/issues/9')
    assert stored['interests'] == ['Italian Game', 'History']
    fail[0] = True
    page.locator('#currentInterests').fill('Chess endgames')
    page.locator('#saveInterests').click()
    expect(page.locator('#interestsFeedback')).to_contain_text('403')
    assert page.locator('#currentInterests').input_value() == 'Chess endgames'
    assert stored['interests'] == ['Italian Game', 'History']
    context.close()
