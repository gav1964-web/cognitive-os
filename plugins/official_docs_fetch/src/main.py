"""Fetch allowlisted official documentation as evidence metadata."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_ALLOWED_DOMAINS = {
    "docs.python.org",
    "docs.pydantic.dev",
    "fastapi.tiangolo.com",
    "docs.djangoproject.com",
    "flask.palletsprojects.com",
    "requests.readthedocs.io",
    "openpyxl.readthedocs.io",
    "pandas.pydata.org",
    "developer.mozilla.org",
    "docs.openai.com",
}


def run(payload: dict[str, object]) -> dict[str, object]:
    url = str(payload["url"]).strip()
    max_chars = max(500, min(int(payload.get("max_chars", 4000)), 12000))
    allowed = _allowed_domains(payload.get("allowed_domains"))
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if parsed.scheme not in {"https", "http"} or not domain:
        raise ValueError("official_docs_fetch requires an absolute http(s) URL")
    if not _domain_allowed(domain, allowed):
        raise ValueError(f"official_docs_fetch domain is not allowlisted: {domain}")
    html = _fetch(url)
    parser = _TextParser()
    parser.feed(html)
    text = " ".join(parser.text.split())[:max_chars]
    return {
        "source": "official_docs_fetch",
        "url": url,
        "domain": domain,
        "title": parser.title.strip(),
        "text_excerpt": text,
        "content_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "fetched_chars": len(text),
    }


def _fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "cognitive-os-official-docs-fetch"})
    with urlopen(request, timeout=10) as response:  # nosec: URL domain is allowlist-checked above
        return response.read().decode("utf-8", errors="replace")


def _allowed_domains(value: object) -> set[str]:
    if not isinstance(value, list):
        return set(DEFAULT_ALLOWED_DOMAINS)
    domains = {str(item).strip().lower() for item in value if str(item).strip()}
    return domains or set(DEFAULT_ALLOWED_DOMAINS)


def _domain_allowed(domain: str, allowed: set[str]) -> bool:
    return any(domain == item or domain.endswith("." + item) for item in allowed)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text = ""
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        else:
            self.text += " " + data
