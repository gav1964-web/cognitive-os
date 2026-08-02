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
        "\n\n"
        "def test_parser_handles_empty_or_malformed_html():\n"
        "    assert parse_news_items('') == []\n"
        "    assert parse_news_items('<html><body>missing article</body></html>') == []\n"
        "\n\n"
        "def test_parser_extracts_news_link_fallback():\n"
        "    html = \"<a href='/news/2026/07/22/example.html'>Очень важная новость про технологии</a>\"\n"
        "    rows = parse_news_items(html)\n"
        "    assert rows[0]['url'] == 'https://www.ixbt.com/news/2026/07/22/example.html'\n"
        "    assert rows[0]['title'] == 'Очень важная новость про технологии'\n"
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

def _test_cli(case_name: str) -> str:
    if case_name == "ixbt_news_scraper":
        return (
            "import csv\n\n"
            "from ixbt_news_scraper.cli import main\n\n\n"
            "def test_cli_writes_csv_from_fixture_without_network(tmp_path):\n"
            "    output = tmp_path / 'news.csv'\n"
            "    assert main(['tests/fixtures/ixbt_news.html', str(output)]) == 0\n"
            "    rows = list(csv.DictReader(output.open(encoding='utf-8')))\n"
            "    assert rows[0]['title'] == 'Example news'\n"
        )
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
