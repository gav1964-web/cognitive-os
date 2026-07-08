import time
from pathlib import Path

import requests


def fetch_html(url: str) -> str:
    last_error = None
    for _ in range(3):
        try:
            return requests.get(url, timeout=5).text
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(0.1)
    cached = Path("cache.html")
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    raise RuntimeError(str(last_error))


def parse_links(html: str) -> list[str]:
    return [part.split('"', 1)[0] for part in html.split('href="')[1:]]


def save_cache(html: str) -> None:
    Path("cache.html").write_text(html, encoding="utf-8")


def scrape(url: str) -> list[str]:
    html = fetch_html(url)
    save_cache(html)
    return parse_links(html)
