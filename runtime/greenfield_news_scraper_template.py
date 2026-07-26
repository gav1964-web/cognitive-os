"""General Stage 2 news-site scraper CLI template."""

from __future__ import annotations


CASE = "news_site_scraper_cli"


def expected_artifacts() -> list[str]:
    return [
        "pyproject.toml",
        "README.md",
        "src/news_site_scraper/__init__.py",
        "src/news_site_scraper/cli.py",
        "src/news_site_scraper/fetcher.py",
        "src/news_site_scraper/parser.py",
        "src/news_site_scraper/csv_writer.py",
        "src/news_site_scraper/site_profile.py",
        "tests/fixtures/news_page.html",
        "tests/test_parser.py",
        "tests/test_csv_writer.py",
        "tests/test_cli.py",
    ]


def acceptance_for(verification: dict[str, object]) -> list[str]:
    if verification.get("status") != "passed":
        return []
    return [
        "parser works from fixture without network",
        "CLI writes a CSV file with stable header",
        "site URL is handled through a profile instead of hardcoded one-site logic",
        "network call has timeout and identifiable user-agent",
        "live access is optional and not required for default tests",
        "all tests run from generated project root",
    ]


def content_for(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path.endswith("news_page.html"):
        return _fixture()
    if path.endswith("test_parser.py"):
        return _test_parser()
    if path.endswith("test_csv_writer.py"):
        return _test_csv_writer()
    if path.endswith("test_cli.py"):
        return _test_cli()
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("fetcher.py"):
        return _fetcher()
    if path.endswith("parser.py"):
        return _parser()
    if path.endswith("csv_writer.py"):
        return _csv_writer()
    if path.endswith("site_profile.py"):
        return _site_profile()
    return "# Generated Stage 2 news scraper placeholder.\n"


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "news_site_scraper"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )


def _readme(prompt: str) -> str:
    return (
        "# news_site_scraper\n\n"
        f"Prompt: {prompt}\n\n"
        "Fixture-first CLI for scraping news links from a site front page into UTF-8 CSV.\n"
        "The site URL is converted into a small profile so ixbt.com, cnews.ru, 3dnews.ru "
        "and similar news pages use the same parser contract instead of one hardcoded scraper.\n\n"
        "Run tests: `python -m pytest tests -q`.\n\n"
        "Example: `python -m news_site_scraper.cli tests/fixtures/news_page.html out.csv --base-url https://3dnews.ru/`.\n"
        "Live URLs are optional and should be used as a separate smoke with rate limits.\n"
    )


def _cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n"
        "from pathlib import Path\n\n"
        "from news_site_scraper.csv_writer import write_news_csv\n"
        "from news_site_scraper.fetcher import fetch_html\n"
        "from news_site_scraper.parser import parse_news_items\n"
        "from news_site_scraper.site_profile import profile_for\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output')\n"
        "    parser.add_argument('--base-url', default=None)\n"
        "    args = parser.parse_args(argv)\n"
        "    is_url = args.input.startswith(('http://', 'https://'))\n"
        "    base_url = args.base_url or (args.input if is_url else 'https://example.test/')\n"
        "    profile = profile_for(base_url)\n"
        "    html = fetch_html(args.input) if is_url else Path(args.input).read_text(encoding='utf-8')\n"
        "    rows = parse_news_items(html, profile)\n"
        "    write_news_csv(args.output, rows)\n"
        "    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _fetcher() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from urllib.request import Request, urlopen\n\n\n"
        "DEFAULT_USER_AGENT = 'cognitive-os-news-scraper/0.1'\n\n\n"
        "def fetch_html(url: str, *, timeout: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> str:\n"
        "    request = Request(url, headers={'User-Agent': user_agent})\n"
        "    with urlopen(request, timeout=timeout) as response:\n"
        "        encoding = response.headers.get_content_charset() or 'utf-8'\n"
        "        return response.read().decode(encoding, errors='replace')\n"
    )


def _site_profile() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from dataclasses import dataclass\n"
        "from urllib.parse import urlparse\n\n\n"
        "@dataclass(frozen=True)\n"
        "class SiteProfile:\n"
        "    base_url: str\n"
        "    source: str\n"
        "    link_markers: tuple[str, ...]\n\n\n"
        "def profile_for(base_url: str) -> SiteProfile:\n"
        "    parsed = urlparse(base_url if '://' in base_url else 'https://' + base_url)\n"
        "    host = parsed.netloc or parsed.path\n"
        "    root = f'{parsed.scheme or \"https\"}://{host}'\n"
        "    if '3dnews.ru' in host:\n"
        "        return SiteProfile(root + '/', '3dnews.ru', ('/news/', '/software-news/', '/hardware-news/'))\n"
        "    if 'cnews.ru' in host:\n"
        "        return SiteProfile(root + '/', 'cnews.ru', ('/news/', '/reviews/', '/articles/'))\n"
        "    if 'ixbt.com' in host:\n"
        "        return SiteProfile(root + '/', 'ixbt.com', ('/news/',))\n"
        "    return SiteProfile(root + '/', host or 'unknown', ('/news/', '/article/', '/articles/'))\n"
    )


def _parser() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from html.parser import HTMLParser\n"
        "from urllib.parse import urljoin\n\n"
        "from news_site_scraper.site_profile import SiteProfile\n\n\n"
        "class _ArticleParser(HTMLParser):\n"
        "    def __init__(self, profile: SiteProfile) -> None:\n"
        "        super().__init__()\n"
        "        self.profile = profile\n"
        "        self.items: list[dict[str, str]] = []\n"
        "        self._current: dict[str, str] | None = None\n"
        "        self._field: str | None = None\n\n"
        "    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:\n"
        "        data = {key: value or '' for key, value in attrs}\n"
        "        if tag == 'article':\n"
        "            self._current = _empty_item(self.profile)\n"
        "        elif self._current is not None and tag == 'a' and data.get('href'):\n"
        "            self._field = 'title'\n"
        "            self._current['url'] = urljoin(self.profile.base_url, data['href'].split('#', 1)[0])\n"
        "        elif self._current is not None and tag == 'time':\n"
        "            self._field = 'date'\n"
        "            self._current['date'] = data.get('datetime') or ''\n"
        "        elif self._current is not None and tag in {'p', 'span'} and not self._current.get('summary'):\n"
        "            self._field = 'summary'\n\n"
        "    def handle_data(self, data: str) -> None:\n"
        "        if self._current is None or self._field is None:\n"
        "            return\n"
        "        if self._field == 'date' and self._current['date']:\n"
        "            return\n"
        "        self._current[self._field] = _squash(self._current[self._field] + ' ' + data)\n\n"
        "    def handle_endtag(self, tag: str) -> None:\n"
        "        if tag in {'a', 'time', 'p', 'span'}:\n"
        "            self._field = None\n"
        "        if tag == 'article' and self._current is not None:\n"
        "            if _valid_item(self._current):\n"
        "                self.items.append(self._current)\n"
        "            self._current = None\n\n\n"
        "class _LinkParser(HTMLParser):\n"
        "    def __init__(self, profile: SiteProfile) -> None:\n"
        "        super().__init__()\n"
        "        self.profile = profile\n"
        "        self.items: list[dict[str, str]] = []\n"
        "        self._current: dict[str, str] | None = None\n\n"
        "    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:\n"
        "        href = dict(attrs).get('href') if tag == 'a' else None\n"
        "        if href and any(marker in href for marker in self.profile.link_markers) and '#comments' not in href:\n"
        "            self._current = _empty_item(self.profile)\n"
        "            self._current['url'] = urljoin(self.profile.base_url, href.split('#', 1)[0])\n\n"
        "    def handle_data(self, data: str) -> None:\n"
        "        if self._current is not None:\n"
        "            self._current['title'] = _squash(self._current['title'] + ' ' + data)\n\n"
        "    def handle_endtag(self, tag: str) -> None:\n"
        "        if tag == 'a' and self._current is not None:\n"
        "            if _valid_item(self._current):\n"
        "                self.items.append(self._current)\n"
        "            self._current = None\n\n\n"
        "def parse_news_items(html: str, profile: SiteProfile) -> list[dict[str, str]]:\n"
        "    article_parser = _ArticleParser(profile)\n"
        "    article_parser.feed(html)\n"
        "    rows = article_parser.items or _parse_link_fallback(html, profile)\n"
        "    seen: set[str] = set()\n"
        "    unique: list[dict[str, str]] = []\n"
        "    for row in rows:\n"
        "        if row['url'] in seen:\n"
        "            continue\n"
        "        seen.add(row['url'])\n"
        "        unique.append(row)\n"
        "    return unique\n\n\n"
        "def _parse_link_fallback(html: str, profile: SiteProfile) -> list[dict[str, str]]:\n"
        "    parser = _LinkParser(profile)\n"
        "    parser.feed(html)\n"
        "    return parser.items\n\n\n"
        "def _empty_item(profile: SiteProfile) -> dict[str, str]:\n"
        "    return {'title': '', 'url': '', 'date': '', 'summary': '', 'source': profile.source}\n\n\n"
        "def _valid_item(item: dict[str, str]) -> bool:\n"
        "    title = item.get('title', '').strip()\n"
        "    return len(title) >= 8 and bool(item.get('url')) and title.lower() not in {'новости', 'лента новостей'}\n\n\n"
        "def _squash(value: str) -> str:\n"
        "    return ' '.join(value.split())\n"
    )


def _csv_writer() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import csv\n"
        "from pathlib import Path\n\n\n"
        "FIELDS = ['title', 'url', 'date', 'summary', 'source']\n\n\n"
        "def write_news_csv(path: str, rows: list[dict[str, str]]) -> None:\n"
        "    target = Path(path)\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with target.open('w', newline='', encoding='utf-8') as handle:\n"
        "        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction='ignore')\n"
        "        writer.writeheader()\n"
        "        writer.writerows(rows)\n"
    )


def _fixture() -> str:
    return (
        "<html><body>\n"
        "<article><a href='/news/2026/example-one.html'>Example 3DNews item</a>"
        "<time datetime='2026-07-22'>22 July 2026</time>"
        "<p>Short summary</p></article>\n"
        "<a href='/news/2026/example-two.html'>Fallback technology news item</a>\n"
        "</body></html>\n"
    )


def _test_parser() -> str:
    return (
        "from pathlib import Path\n\n"
        "from news_site_scraper.parser import parse_news_items\n"
        "from news_site_scraper.site_profile import profile_for\n\n\n"
        "def test_parser_extracts_article_fixture_news():\n"
        "    html = Path('tests/fixtures/news_page.html').read_text(encoding='utf-8')\n"
        "    rows = parse_news_items(html, profile_for('https://3dnews.ru/'))\n"
        "    assert rows[0]['title'] == 'Example 3DNews item'\n"
        "    assert rows[0]['date'] == '2026-07-22'\n"
        "    assert rows[0]['url'] == 'https://3dnews.ru/news/2026/example-one.html'\n"
        "    assert rows[0]['source'] == '3dnews.ru'\n\n\n"
        "def test_parser_handles_empty_or_malformed_html():\n"
        "    assert parse_news_items('', profile_for('https://3dnews.ru/')) == []\n"
        "    assert parse_news_items('<html><body>missing article</body></html>', profile_for('https://3dnews.ru/')) == []\n\n\n"
        "def test_parser_extracts_news_link_fallback_and_deduplicates():\n"
        "    html = \"<a href='/news/2026/example.html'>Очень важная новость про технологии</a>\" * 2\n"
        "    rows = parse_news_items(html, profile_for('https://3dnews.ru/'))\n"
        "    assert len(rows) == 1\n"
        "    assert rows[0]['url'] == 'https://3dnews.ru/news/2026/example.html'\n"
    )


def _test_csv_writer() -> str:
    return (
        "import csv\n\n"
        "from news_site_scraper.csv_writer import FIELDS, write_news_csv\n\n\n"
        "def test_csv_writer_writes_stable_header(tmp_path):\n"
        "    output = tmp_path / 'news.csv'\n"
        "    write_news_csv(str(output), [{'title':'T','url':'U','date':'D','summary':'','source':'3dnews.ru'}])\n"
        "    assert list(csv.reader(output.open(encoding='utf-8')))[0] == FIELDS\n"
    )


def _test_cli() -> str:
    return (
        "import csv\n\n"
        "from news_site_scraper.cli import main\n\n\n"
        "def test_cli_writes_csv_from_fixture_without_network(tmp_path):\n"
        "    output = tmp_path / 'news.csv'\n"
        "    assert main(['tests/fixtures/news_page.html', str(output), '--base-url', 'https://3dnews.ru/']) == 0\n"
        "    rows = list(csv.DictReader(output.open(encoding='utf-8')))\n"
        "    assert rows[0]['title'] == 'Example 3DNews item'\n"
        "    assert rows[0]['source'] == '3dnews.ru'\n"
    )
