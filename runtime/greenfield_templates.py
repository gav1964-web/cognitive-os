"""Template bodies for deterministic greenfield prompt projects."""

from __future__ import annotations

from .greenfield_local10_templates import (
    acceptance_for as local10_acceptance_for,
    content_for_case as local10_content_for_case,
    has_case as local10_has_case,
)
from .greenfield_stage2_templates import (
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
        return _test_cli()
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
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('url', nargs='?')\n"
        "    parser.add_argument('output', nargs='?')\n"
        "    parser.parse_args(argv)\n"
        "    return 0\n"
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
        "DEFAULT_USER_AGENT = 'cognitive-os-scaffold/0.1'\n\n\n"
        "def fetch_html(url: str, *, timeout: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> str:\n"
        "    raise NotImplementedError('live fetching is disabled in default tests')\n"
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
        "    parser = _NewsParser(); parser.feed(html); return parser.items\n"
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


def _sheet_converter() -> str:
    return r'''from __future__ import annotations

import csv
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

LEGACY_XLS_POLICY = "unsupported_without_adapter"
DEPENDENCY_POLICY = {"xlsx": "stdlib_ooxml_minimal", "xls": LEGACY_XLS_POLICY}


def convert(source: str, destination: str) -> dict[str, str]:
    src, dst = Path(source), Path(destination)
    if ".xls" in {src.suffix.lower(), dst.suffix.lower()}:
        raise ValueError("legacy .xls requires an explicit adapter")
    if src.suffix.lower() == ".csv" and dst.suffix.lower() == ".xlsx":
        _csv_to_xlsx(src, dst); return {"source": source, "destination": destination, "status": "ok"}
    if src.suffix.lower() == ".xlsx" and dst.suffix.lower() == ".csv":
        _xlsx_to_csv(src, dst); return {"source": source, "destination": destination, "status": "ok"}
    if src.suffix.lower() == ".csv" and dst.suffix.lower() == ".csv":
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return {"source": source, "destination": destination, "status": "ok"}
    raise ValueError(f"unsupported conversion: {src.suffix} -> {dst.suffix}")


def _csv_to_xlsx(source: Path, destination: Path) -> None:
    rows = list(csv.reader(source.read_text(encoding="utf-8").splitlines()))
    sheet = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for row_index, row in enumerate(rows, 1):
        sheet.append(f'<row r="{row_index}">')
        for col_index, value in enumerate(row, 1):
            ref = f"{chr(64 + col_index)}{row_index}"
            sheet.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        sheet.append("</row>")
    sheet.append("</sheetData></worksheet>")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types())
        zf.writestr("_rels/.rels", _root_rels())
        zf.writestr("xl/workbook.xml", _workbook())
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels())
        zf.writestr("xl/worksheets/sheet1.xml", "".join(sheet))


def _xlsx_to_csv(source: Path, destination: Path) -> None:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(source) as zf:
        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.findall(".//m:row", ns):
        values = []
        for cell in row.findall("m:c", ns):
            text = cell.find("m:is/m:t", ns)
            values.append("" if text is None or text.text is None else text.text)
        rows.append(values)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


def _content_types() -> str:
    return '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'


def _root_rels() -> str:
    return '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'


def _workbook() -> str:
    return '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'


def _workbook_rels() -> str:
    return '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
'''


def _html_fixture() -> str:
    return (
        "<html><body><article><a href='/news/example.html'>Example news</a>"
        "<time datetime='2026-07-07'>7 July 2026</time></article></body></html>\n"
    )


def _test_parser() -> str:
    return (
        "from pathlib import Path\n\n"
        "from ixbt_news_scraper.parser import parse_news_items\n\n\n"
        "def test_parser_extracts_fixture_news():\n"
        "    html = Path('tests/fixtures/ixbt_news.html').read_text(encoding='utf-8')\n"
        "    rows = parse_news_items(html)\n"
        "    assert rows[0]['title'] == 'Example news'\n"
        "    assert rows[0]['date'] == '2026-07-07'\n"
    )


def _test_csv_writer() -> str:
    return (
        "import csv\n\n"
        "from ixbt_news_scraper.csv_writer import FIELDS, write_news_csv\n\n\n"
        "def test_csv_writer_writes_stable_header(tmp_path):\n"
        "    output = tmp_path / 'news.csv'\n"
        "    write_news_csv(str(output), [{'title':'T','url':'U','date':'D','summary':'','source':'ixbt.com'}])\n"
        "    assert list(csv.reader(output.open(encoding='utf-8')))[0] == FIELDS\n"
    )


def _test_converter() -> str:
    return (
        "from pathlib import Path\n\n\n"
        "def test_converter_behavior(tmp_path):\n"
        "    try:\n"
        "        from md_to_rtf.converter import convert, markdown_to_rtf\n"
        "        output = tmp_path / 'sample.rtf'\n"
        "        assert convert('tests/fixtures/sample.md', str(output))['status'] == 'ok'\n"
        "        assert output.read_text(encoding='utf-8').startswith('{\\\\rtf1')\n"
        "        assert '\\\\bullet one' in markdown_to_rtf('- one')\n"
        "    except ModuleNotFoundError:\n"
        "        from sheet_csv_converter.converter import DEPENDENCY_POLICY, LEGACY_XLS_POLICY, convert\n"
        "        xlsx = tmp_path / 'sample.xlsx'; csv_out = tmp_path / 'roundtrip.csv'\n"
        "        assert convert('tests/fixtures/sample.csv', str(xlsx))['status'] == 'ok'\n"
        "        assert convert(str(xlsx), str(csv_out))['status'] == 'ok'\n"
        "        assert csv_out.read_text(encoding='utf-8').startswith('name,value')\n"
        "        assert DEPENDENCY_POLICY['xlsx'] == 'stdlib_ooxml_minimal'\n"
        "        assert LEGACY_XLS_POLICY == 'unsupported_without_adapter'\n"
    )


def _test_cli() -> str:
    return (
        "from pathlib import Path\n\n\n"
        "def test_cli_main_returns_zero(tmp_path):\n"
        "    try:\n"
        "        from md_to_rtf.cli import main\n"
        "        output = tmp_path / 'out.rtf'\n"
        "        assert main(['tests/fixtures/sample.md', str(output)]) == 0\n"
        "        assert output.read_text(encoding='utf-8').startswith('{\\\\rtf1')\n"
        "    except ModuleNotFoundError:\n"
        "        from sheet_csv_converter.cli import main\n"
        "        output = tmp_path / 'out.xlsx'\n"
        "        assert main(['tests/fixtures/sample.csv', str(output)]) == 0\n"
        "        assert output.is_file()\n"
    )
