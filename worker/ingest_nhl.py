"""Read official NHL team headline metadata, never full article bodies."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta":
            key = values.get("property") or values.get("name")
            if key and values.get("content"):
                self.meta[key] = values["content"]
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])


def parse_article(text, url):
    page = PageMetadata()
    page.feed(text)
    # NHL serializes its NewsArticle metadata inside the page's JSON state.
    # Support both ordinary JSON-LD and JSON strings escaped by the framework.
    published = re.search(r'\\?"datePublished\\?"\s*:\s*\\?"([^"\\]+)', text)
    return {"title": page.meta.get("og:title", "").split(" | ")[0],
            "summary": page.meta.get("og:description") or page.meta.get("description", ""),
            "published": published.group(1) if published else None, "link": url,
            "image_url": page.meta.get("og:image")}


def fetch_articles(source, index_text, *, timeout=8, limit=12):
    import requests
    page = PageMetadata()
    page.feed(index_text)
    base = urlsplit(source["url"])
    prefix = base.path.rstrip("/") + "/"
    urls = []
    for link in page.links:
        url = urljoin(source["url"], link)
        parsed = urlsplit(url)
        if parsed.hostname == base.hostname and parsed.path.startswith(prefix) and url not in urls:
            urls.append(url)

    def fetch(url):
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "ScrollForge/1.0 (+https://github.com/floogle11/scrollforge)"})
            response.raise_for_status()
            return parse_article(response.text, url)
        except requests.RequestException:
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        return [entry for entry in pool.map(fetch, urls[:min(limit, 12)]) if entry]
