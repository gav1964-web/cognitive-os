from __future__ import annotations

from runtime.greenfield_local10_templates import (
    acceptance_for as local10_acceptance_for,
    content_for_case as local10_content_for_case,
    has_case as local10_has_case,
)
from runtime.greenfield_stage2_templates import (
    acceptance_for as stage2_acceptance_for,
    content_for_case as stage2_content_for_case,
    has_case as stage2_has_case,
)


def acceptance_covered(case_name: str, verification: dict[str, object]) -> list[str]:
    if stage2_has_case(case_name):
        return stage2_acceptance_for(case_name, verification)
    if local10_has_case(case_name):
        return local10_acceptance_for(case_name, verification)
    if verification.get("status") != "passed":
        return []
    if case_name == "ixbt_news_scraper":
        return [
            "parser works from fixture without network",
            "CLI writes a CSV file with stable header",
            "network call has timeout and identifiable user-agent",
            "live access is optional and not required for default tests",
            "all tests run from generated project root",
        ]
    if case_name == "markdown_to_rtf_cli":
        return [
            "CLI accepts input and output paths",
            "converter produces valid RTF envelope",
            "tests do not require external services",
            "all tests run from generated project root",
        ]
    if case_name == "xlsx_csv_converter":
        return [
            "xlsx to csv conversion is covered by tests",
            "csv to xlsx conversion is covered by tests",
            "legacy xls limitation or adapter is explicit",
            "all tests run from generated project root",
        ]
    return []

def content_for(artifact: str, case_name: str, prompt: str) -> str:
    path = artifact.replace("\\", "/")
    if stage2_has_case(case_name):
        return stage2_content_for_case(artifact, case_name, prompt)
    if path == "pyproject.toml":
        return _pyproject(case_name.replace("-", "_"))
    if path == "README.md":
        return f"# {case_name}\n\nPrompt: {prompt}\n\nStatus: generated curriculum project.\n\nRun tests: `python -m pytest tests -q`.\n"
    if local10_has_case(case_name):
        return local10_content_for_case(artifact, case_name)
    if path.endswith("test_parser.py"):
        return _test_parser()
    if path.endswith("test_csv_writer.py"):
        return _test_csv_writer()
    if path.endswith("test_converter.py"):
        return _test_converter()
    if path.endswith("test_cli.py"):
        return _test_cli(case_name)
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("cli.py"):
        return _cli_module(case_name)
    if path.endswith("contracts.py"):
        return _contracts_module()
    if path.endswith("fetcher.py"):
        return _fetcher_module()
    if path.endswith("parser.py"):
        return _parser_module()
    if path.endswith("csv_writer.py"):
        return _csv_writer_module()
    if path.endswith("converter.py"):
        return _converter_module(case_name)
    if "/fixtures/" in path and path.endswith(".html"):
        return _html_fixture()
    if "/fixtures/" in path and path.endswith(".md"):
        return "# Sample\n\n- one\n- two\n"
    if "/fixtures/" in path and path.endswith(".csv"):
        return "name,value\nalpha,1\nbeta,2\n"
    return "# Generated scaffold placeholder.\n"

def _pyproject(package: str) -> str:
    return (
        "[project]\n"
        f'name = "{package}"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
    )

def _cli_module(case_name: str) -> str:
    if case_name == "markdown_to_rtf_cli":
        package = "md_to_rtf"
    elif case_name == "xlsx_csv_converter":
        package = "sheet_csv_converter"
    else:
        return _ixbt_cli()
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n\n"
        f"from {package}.converter import convert\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output')\n"
        "    args = parser.parse_args(argv)\n"
        "    convert(args.input, args.output)\n"
        "    return 0\n"
    )

def _ixbt_cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n\n\n"
        "from pathlib import Path\n\n"
        "from ixbt_news_scraper.csv_writer import write_news_csv\n"
        "from ixbt_news_scraper.fetcher import fetch_html\n"
        "from ixbt_news_scraper.parser import parse_news_items\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output')\n"
        "    args = parser.parse_args(argv)\n"
        "    html = fetch_html(args.input) if args.input.startswith(('http://', 'https://')) else Path(args.input).read_text(encoding='utf-8')\n"
        "    rows = parse_news_items(html)\n"
        "    write_news_csv(args.output, rows)\n"
        "    return 0\n"
        "\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )

def _contracts_module() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class ConversionRequest:\n"
        "    source: str\n"
        "    destination: str\n"
        "    mode: str\n"
        "    delimiter: str = ','\n"
        "    encoding: str = 'utf-8'\n\n\n"
        "@dataclass(frozen=True)\n"
        "class ConversionResult:\n"
        "    rows: int\n"
        "    output_path: str\n"
    )

def _fetcher_module() -> str:
    return (
        "from __future__ import annotations\n\n\n"
        "from urllib.request import Request, urlopen\n\n\n"
        "DEFAULT_USER_AGENT = 'cognitive-os-scaffold/0.1'\n\n\n"
        "def fetch_html(url: str, *, timeout: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> str:\n"
        "    request = Request(url, headers={'User-Agent': user_agent})\n"
        "    with urlopen(request, timeout=timeout) as response:\n"
        "        encoding = response.headers.get_content_charset() or 'utf-8'\n"
        "        return response.read().decode(encoding, errors='replace')\n"
    )

def _parser_module() -> str:
    return (
        "from __future__ import annotations\n\n"
        "from html.parser import HTMLParser\n"
        "from urllib.parse import urljoin\n\n\n"
        "class _NewsParser(HTMLParser):\n"
        "    def __init__(self) -> None:\n"
        "        super().__init__(); self.items=[]; self._current=None; self._field=None\n\n"
        "    def handle_starttag(self, tag, attrs):\n"
        "        data = dict(attrs)\n"
        "        if tag == 'article':\n"
        "            self._current = {'title':'','url':'','date':'','summary':'','source':'ixbt.com'}\n"
        "        elif self._current is not None and tag == 'a':\n"
        "            self._field = 'title'; self._current['url'] = urljoin('https://www.ixbt.com', data.get('href') or '')\n"
        "        elif self._current is not None and tag == 'time':\n"
        "            self._field = 'date'; self._current['date'] = data.get('datetime') or ''\n\n"
        "    def handle_data(self, data):\n"
        "        if self._current is not None and self._field:\n"
        "            if self._field == 'date' and self._current['date']:\n"
        "                return\n"
        "            self._current[self._field] = ' '.join((self._current[self._field] + ' ' + data).split())\n\n"
        "    def handle_endtag(self, tag):\n"
        "        if tag in {'a','time'}: self._field = None\n"
        "        if tag == 'article' and self._current is not None:\n"
        "            if self._current['title'] and self._current['url']: self.items.append(self._current)\n"
        "            self._current = None\n\n\n"
        "def parse_news_items(html: str) -> list[dict[str, str]]:\n"
        "    parser = _NewsParser(); parser.feed(html)\n"
        "    return parser.items or _parse_news_links(html)\n\n\n"
        "class _NewsLinkParser(HTMLParser):\n"
        "    def __init__(self) -> None:\n"
        "        super().__init__(); self.items=[]; self._current=None\n\n"
        "    def handle_starttag(self, tag, attrs):\n"
        "        href = dict(attrs).get('href') if tag == 'a' else None\n"
        "        if href and '/news/' in href and '#comments' not in href:\n"
        "            self._current = {'title':'', 'url': urljoin('https://www.ixbt.com', href.split('#', 1)[0]), 'date':'', 'summary':'', 'source':'ixbt.com'}\n\n"
        "    def handle_data(self, data):\n"
        "        if self._current is not None:\n"
        "            self._current['title'] = ' '.join((self._current['title'] + ' ' + data).split())\n\n"
        "    def handle_endtag(self, tag):\n"
        "        if tag == 'a' and self._current is not None:\n"
        "            title = self._current['title'].strip()\n"
        "            if len(title) >= 20 and title.lower() not in {'лента новостей'}:\n"
        "                self.items.append(self._current)\n"
        "            self._current = None\n\n\n"
        "def _parse_news_links(html: str) -> list[dict[str, str]]:\n"
        "    parser = _NewsLinkParser(); parser.feed(html)\n"
        "    seen=set(); rows=[]\n"
        "    for item in parser.items:\n"
        "        if item['url'] in seen:\n"
        "            continue\n"
        "        seen.add(item['url']); rows.append(item)\n"
        "    return rows\n"
    )

def _csv_writer_module() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import csv\n"
        "from pathlib import Path\n\n\n"
        "FIELDS = ['title', 'url', 'date', 'summary', 'source']\n\n\n"
        "def write_news_csv(path: str, rows: list[dict[str, str]]) -> None:\n"
        "    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with target.open('w', newline='', encoding='utf-8') as handle:\n"
        "        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)\n"
    )

def _converter_module(case_name: str) -> str:
    if case_name == "markdown_to_rtf_cli":
        return _markdown_converter()
    if case_name == "xlsx_csv_converter":
        return _sheet_converter()
    return "def convert(source: str, destination: str) -> dict[str, str]:\n    return {'status': 'not_implemented'}\n"

def _markdown_converter() -> str:
    return (
        "from pathlib import Path\n\n\n"
        "def markdown_to_rtf(markdown: str) -> str:\n"
        "    lines = []\n"
        "    for raw in markdown.splitlines():\n"
        "        text = _escape(raw.lstrip('#- ').strip())\n"
        "        if raw.startswith('# '): lines.append(r'\\b ' + text + r'\\b0\\par')\n"
        "        elif raw.startswith('- '): lines.append(r'\\bullet ' + text + r'\\par')\n"
        "        elif text: lines.append(text + r'\\par')\n"
        "    return r'{\\rtf1\\ansi ' + ''.join(lines) + '}'\n\n\n"
        "def convert(source: str, destination: str) -> dict[str, str]:\n"
        "    Path(destination).write_text(markdown_to_rtf(Path(source).read_text(encoding='utf-8')), encoding='utf-8')\n"
        "    return {'source': source, 'destination': destination, 'status': 'ok'}\n\n\n"
        "def _escape(value: str) -> str:\n"
        "    return value.replace('\\\\', r'\\\\').replace('{', r'\\{').replace('}', r'\\}')\n"
    )
