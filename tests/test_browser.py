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


def _two_card_feed():
    challenge = {
        "id": "browser-challenge", "created_at": "2026-10-24T16:00:00Z", "category": "CHALLENGE_CURRENT",
        "course_tag": "ME-3310", "title": "Browser test challenge",
        "body_markdown": "Safe text <img src=x onerror=window.__xss=1> and [bad](javascript:window.__xss=2)",
        "solution_markdown": "Test solution **with emphasis**.", "source_url": None, "parent_card_id": None,
        "comments": [
            {"id": "browser-user", "author": "USER", "body_markdown": "Question?", "created_at": "2026-10-24T16:01:00Z", "unread": False, "issue_number": None},
            {"id": "browser-codex", "author": "CODEX", "body_markdown": "Sample reply.", "created_at": "2026-10-24T16:02:00Z", "unread": True, "issue_number": None},
        ],
    }
    sports = {
        "id": "browser-sample", "created_at": "2026-10-24T15:00:00Z", "category": "SPORTS",
        "course_tag": None, "title": "SAMPLE: Browser navigation sample", "body_markdown": "Sample archive item.",
        "solution_markdown": None, "source_url": None, "parent_card_id": None, "comments": [],
    }
    return {"last_updated": "2026-10-24T17:00:00Z", "calendar_mode": "BASELINE",
            "active_exam_course": None, "cards": [challenge, sports]}


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["mobile", "desktop"])
def test_pwa_paths_navigation_settings_inbox_issue_post_and_markdown(browser, site_url, viewport):
    context = browser.new_context(viewport=viewport, service_workers="block")
    page = context.new_page()
    feed = _two_card_feed()
    page.route("**/data/feed.json", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(feed)))
    issue_posts = []
    def github_issue(route):
        issue_posts.append({"url": route.request.url, "headers": route.request.headers, "body": json.loads(route.request.post_data)})
        route.fulfill(status=201, content_type="application/json", body=json.dumps({"number": 42}))
    page.route("https://api.github.com/repos/owner/repo/issues", github_issue)
    # Avoid external font/math CDN dependency; behavior should remain local and usable.
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    try:
        response = page.goto(site_url, wait_until="domcontentloaded")
        assert response and response.ok
        page.locator(".feed-card").wait_for()
        assert page.locator("#cardPosition").inner_text().strip() == "01 / 02"
        assert page.locator(".feed-card").evaluate("el => el.dataset.cardId") in {"browser-challenge", "browser-sample"}
        assert page.locator("img").count() == 0
        assert page.evaluate("window.__xss || 0") == 0
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        results = ROOT / "test-results"
        results.mkdir(exist_ok=True)
        screenshot = "xss-mobile.png" if viewport["width"] == 390 else "xss-desktop.png"
        page.wait_for_timeout(300)
        page.screenshot(path=str(results / screenshot), full_page=True)

        page.keyboard.press("j")
        assert page.locator("#cardPosition").inner_text().strip() == "02 / 02"
        page.keyboard.press("k")
        assert page.locator("#cardPosition").inner_text().strip() == "01 / 02"
        # Locate the challenge independent of randomized initial ordering.
        for _ in range(2):
            if page.locator(".feed-card").get_attribute("data-card-id") == "browser-challenge":
                break
            page.locator("#nextButton").click()
        assert page.locator(".feed-card").get_attribute("data-card-id") == "browser-challenge"

        page.locator(".solution-toggle").click()
        assert page.locator(".solution-panel").evaluate("el => el.classList.contains('open')")
        assert page.locator(".solution-content strong").inner_text() == "with emphasis"
        page.locator(".comment-toggle").click()
        assert page.locator(".card-comments").evaluate("el => el.classList.contains('open')")
        page.keyboard.press("c")
        assert not page.locator(".card-comments").evaluate("el => el.classList.contains('open')")
        page.keyboard.press("c")
        assert page.locator(".card-comments").evaluate("el => el.classList.contains('open')")

        page.locator("#settingsButton").click()
        assert page.locator("#settingsModal").is_visible()
        page.locator("#repoSlug").fill("owner/repo")
        page.locator("#repoToken").fill("test-token")
        page.locator("#settingsForm button[type=submit]").click()
        assert "CONFIGURATION SAVED" in page.locator("#settingsFeedback").inner_text()
        assert page.evaluate("localStorage.getItem('scrollforge.repo_slug')") == "owner/repo"
        page.keyboard.press("Escape")
        assert not page.locator("#settingsModal").is_visible()

        page.locator("#inboxButton").click()
        assert page.locator("#inboxDrawer").evaluate("el => el.classList.contains('open')")
        assert page.locator(".inbox-item").count() == 1
        page.locator(".inbox-item").click()
        assert page.locator(".feed-card").get_attribute("data-card-id") == "browser-challenge"
        assert page.locator("#inboxDrawer").get_attribute("aria-hidden") == "true"

        textarea = page.locator("textarea[name=comment]")
        textarea.fill("Can you show the units?")
        page.locator(".comment-form button[type=submit]").click()
        page.get_by_text("QUEUED FOR NEXT CODEX RUN").wait_for()
        assert len(issue_posts) == 1
        assert issue_posts[0]["body"]["title"] == "Comment on Card: browser-challenge"
        assert issue_posts[0]["body"]["labels"] == ["pending-codex"]
        assert json.loads(issue_posts[0]["body"]["body"]) == {
            "card_id": "browser-challenge", "course_tag": "ME-3310", "user_comment": "Can you show the units?"
        }
        page.reload(wait_until="domcontentloaded")
        page.locator(".empty-card").wait_for()
        assert "NO UNSEEN SIGNALS" in page.locator(".empty-card").inner_text()
        assert page.evaluate("window.__xss || 0") == 0
    finally:
        context.close()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1440, "height": 1000}], ids=["seed-mobile", "seed-desktop"])
def test_seeded_feed_screenshot_and_viewport_fit(browser, site_url, viewport):
    context = browser.new_context(viewport=viewport, service_workers="block")
    page = context.new_page()
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    try:
        page.goto(site_url, wait_until="domcontentloaded")
        page.locator(".feed-card").wait_for()
        assert page.locator(".feed-card").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        next_box = page.locator("#nextButton").bounding_box()
        assert next_box["y"] + next_box["height"] <= viewport["height"]
        results = ROOT / "test-results"
        results.mkdir(exist_ok=True)
        filename = "mobile.png" if viewport["width"] == 390 else "desktop.png"
        page.wait_for_timeout(300)
        page.screenshot(path=str(results / filename), full_page=True)
    finally:
        context.close()


@pytest.mark.parametrize("mode", ["BASELINE", "EXAM_WINDOW", "CRUNCH_WINDOW", "EXAM_DAY"])
def test_interleaver_retains_challenges_and_limits_runs(browser, site_url, mode):
    context = browser.new_context(service_workers="block")
    page = context.new_page()
    try:
        page.goto(site_url, wait_until="domcontentloaded")
        page.locator(".feed-card").wait_for()
        result = page.evaluate("""mode => {
          const cards = [];
          for (let i = 0; i < 11; i++) cards.push({id: 'c' + i, category: i % 2 ? 'CHALLENGE_CURRENT' : 'CHALLENGE_PAST'});
          for (let i = 0; i < 4; i++) cards.push({id: 'l' + i, category: i % 2 ? 'SPORTS' : 'STORY'});
          const seen = ['l0'];
          const boundary = [{id: 'prior-a', category: 'CHALLENGE_CURRENT'}, {id: 'prior-b', category: 'CHALLENGE_PAST'}];
          const output = window.ScrollForge.interleaveCards(cards, seen, mode, boundary);
          let run = 2;
          for (const card of output) {
            run = card.category.startsWith('CHALLENGE_') ? run + 1 : 0;
            if (run > 2) return {error: 'challenge streak exceeded'};
          }
          const challengeIds = cards.filter(c => c.category.startsWith('CHALLENGE_')).map(c => c.id);
          return {challengeIds, returnedChallengeIds: [...new Set(output.filter(c => c.category.startsWith('CHALLENGE_')).map(c => c.id))]};
        }""", mode)
        assert "error" not in result
        assert set(result["returnedChallengeIds"]) == set(result["challengeIds"])
    finally:
        context.close()


def test_service_worker_serves_seeded_shell_and_feed_offline(browser, site_url):
    context = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="allow")
    page = context.new_page()
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    try:
        page.goto(site_url, wait_until="domcontentloaded")
        page.locator(".feed-card").wait_for()
        page.wait_for_function("!!navigator.serviceWorker.controller", timeout=10000)
        page.reload(wait_until="domcontentloaded")
        page.locator(".feed-card").wait_for()
        context.set_offline(True)
        page.reload(wait_until="domcontentloaded", timeout=10000)
        page.locator(".feed-card").wait_for(timeout=10000)
        assert "OFFLINE" in page.locator("#networkText").inner_text()
        assert page.locator(".card-title").inner_text().strip()
    finally:
        context.close()


def test_delayed_repository_default_preserves_typed_settings(browser, site_url):
    context = browser.new_context(service_workers="block")
    page = context.new_page()
    delayed = []
    page.route("**/data/repo.json", lambda route: delayed.append(route))
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    try:
        page.goto(site_url, wait_until="domcontentloaded")
        page.locator(".feed-card").wait_for()
        page.locator("#settingsButton").click()
        page.locator("#repoSlug").fill("owner/custom-feed")
        page.wait_for_timeout(100)
        assert delayed
        for route in delayed:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"repository": "floogle11/scrollforge"}))
        page.wait_for_timeout(100)
        assert page.locator("#repoSlug").input_value() == "owner/custom-feed"
        page.locator("#settingsForm button[type=submit]").click()
        assert page.evaluate("localStorage.getItem('scrollforge.repo_slug')") == "owner/custom-feed"
    finally:
        context.close()
