"""Image table to Excel CLI template for Stage 2 generated packages."""

from __future__ import annotations


def content_for(path: str, prompt: str) -> str:
    if path == "pyproject.toml":
        return _pyproject()
    if path == "README.md":
        return _readme(prompt)
    if path == "image_table_to_excel.py":
        return _root_cli()
    if path.endswith("__init__.py"):
        return '__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
    if path.endswith("test_core.py"):
        return _test_core()
    if path.endswith("test_cli.py"):
        return _test_cli()
    if path.endswith("cli.py"):
        return _cli()
    if path.endswith("table_extractor.py"):
        return _core()
    if path.endswith("sample.webp"):
        return "fake webp fixture used with injectable OCR backend\n"
    return "# Generated Stage 2 image table to Excel package placeholder.\n"


def _pyproject() -> str:
    return (
        "[project]\n"
        'name = "image_table_excel_cli"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = []\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
        'pythonpath = ["src"]\n'
    )


def _readme(prompt: str) -> str:
    return (
        "# image_table_excel_cli\n\n"
        f"Prompt: {prompt}\n\n"
        "Local CLI utility that reads an image containing a simple price table, extracts rows "
        "through an injectable OCR/text backend, and writes an `.xlsx` workbook with the same "
        "base name as the image by default. Default tests do not require network, OCR engines, "
        "or spreadsheet libraries.\n\n"
        "Run tests: `python -m pytest tests -q`.\n"
        "Run CLI: `python image_table_to_excel.py input.webp`.\n"
        "Run CLI with explicit output: `python image_table_to_excel.py input.webp output.xlsx`.\n\n"
        "Use `--format xlsx`, `--format csv`, `--format xls`, `--format html`, `--format doc`, "
        "or `--format rtf` when output path is omitted. When output path is provided, `.xlsx`, "
        "`.csv`, `.xls`, `.html`, `.doc`, and `.rtf` suffixes select the writer. The `.xls` and "
        "`.doc` writers produce application-compatible HTML tables; the `.rtf` writer produces a "
        "plain Rich Text Format table without external dependencies.\n\n"
        "For deterministic OCR text, use `--ocr-text-file recognized.txt` or set "
        "`IMAGE_TABLE_OCR_TEXT`. For live image understanding, configure an OpenAI-compatible "
        "vision/OCR backend with `IMAGE_TABLE_VISION_BASE_URL`, `IMAGE_TABLE_VISION_MODEL`, "
        "and optional `IMAGE_TABLE_VISION_API_KEY`. The generated workbook is written with a "
        "minimal stdlib OOXML writer.\n"
    )


def _core() -> str:
    return r'''from __future__ import annotations

import base64
import csv
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
SUPPORTED_OUTPUT_EXTENSIONS = {".xlsx", ".csv", ".xls", ".html", ".doc", ".rtf"}
HEADERS = ["Наименование", "Ед.", "Цена", "Кол-во", "Сумма"]


@dataclass(frozen=True)
class TableRow:
    name: str
    unit: str = ""
    price: float | None = None
    quantity: float | None = None
    total: float | None = None


OcrBackend = Callable[[Path], str]


def image_table_to_excel(
    image_path: str,
    output_path: str | None = None,
    *,
    ocr_backend: OcrBackend | None = None,
    ocr_text_file: str | None = None,
    output_format: str = "xlsx",
) -> dict[str, object]:
    source = _validate_image_path(image_path)
    target = _resolve_output_target(source, output_path, output_format)
    text = _resolve_ocr_text(source, ocr_backend=ocr_backend, ocr_text_file=ocr_text_file)
    rows = parse_table_text(text)
    if not rows:
        raise ValueError("no table rows recognized")
    write_table_output(target, rows)
    return {"input_path": str(source), "output_path": str(target), "rows": len(rows)}


def parse_table_text(text: str) -> list[TableRow]:
    rows: list[TableRow] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line or _is_header(line):
            continue
        row = _parse_line(line)
        if row is not None:
            rows.append(row)
    return rows


def write_xlsx(path: Path, rows: list[TableRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = [HEADERS]
    for row in rows:
        table.append(
            [
                row.name,
                row.unit,
                _number_or_blank(row.price),
                _number_or_blank(row.quantity),
                _number_or_blank(row.total),
            ]
        )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types())
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("xl/workbook.xml", _workbook())
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels())
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(table))


def write_table_output(path: Path, rows: list[TableRow]) -> None:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        write_xlsx(path, rows)
    elif suffix == ".csv":
        write_csv(path, rows)
    elif suffix == ".xls":
        write_xls_html(path, rows)
    elif suffix == ".html":
        write_html(path, rows)
    elif suffix == ".doc":
        write_doc_html(path, rows)
    elif suffix == ".rtf":
        write_rtf(path, rows)
    else:
        raise ValueError(f"unsupported output extension: {path.suffix}")


def write_csv(path: Path, rows: list[TableRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow([row.name, row.unit, _number_or_blank(row.price), _number_or_blank(row.quantity), _number_or_blank(row.total)])


def write_xls_html(path: Path, rows: list[TableRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_html_document(rows), encoding="utf-8")


def write_html(path: Path, rows: list[TableRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_html_document(rows), encoding="utf-8")


def write_doc_html(path: Path, rows: list[TableRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_html_document(rows), encoding="utf-8")


def write_rtf(path: Path, rows: list[TableRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["{\\rtf1\\ansi\\deff0", "\\b " + _rtf_escape(" | ".join(HEADERS)) + "\\b0\\par"]
    for row in rows:
        values = [row.name, row.unit, _number_or_blank(row.price), _number_or_blank(row.quantity), _number_or_blank(row.total)]
        lines.append(_rtf_escape(" | ".join(str(value) for value in values)) + "\\par")
    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _rtf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _html_document(rows: list[TableRow]) -> str:
    html_rows = [_html_row(HEADERS)]
    for row in rows:
        html_rows.append(
            _html_row([row.name, row.unit, _number_or_blank(row.price), _number_or_blank(row.quantity), _number_or_blank(row.total)])
        )
    return (
        "<html><head><meta charset=\"utf-8\"></head><body><table>"
        + "".join(html_rows)
        + "</table></body></html>"
    )


def _parse_line(line: str) -> TableRow | None:
    full = re.fullmatch(
        r"(?P<head>.+?)\s+(?P<price>\d+(?:[.,]\d+)?)\s+(?P<quantity>\d+(?:[.,]\d+)?)\s+"
        r"(?P<total>\d{1,3}(?:\s\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)",
        line,
    )
    if full:
        head = full.group("head").split()
        if len(head) < 2:
            return None
        return TableRow(
            name=" ".join(head[:-1]),
            unit=head[-1],
            price=_parse_number(full.group("price")),
            quantity=_parse_number(full.group("quantity")),
            total=_parse_number(full.group("total")),
        )
    total_only = re.fullmatch(r"(?P<name>.+?)\s+(?P<total>\d{1,3}(?:\s\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)", line)
    if total_only:
        return TableRow(name=total_only.group("name"), total=_parse_number(total_only.group("total")))
    return None


def _resolve_ocr_text(
    image_path: Path,
    *,
    ocr_backend: OcrBackend | None = None,
    ocr_text_file: str | None = None,
) -> str:
    if ocr_backend is not None:
        return ocr_backend(image_path)
    if ocr_text_file:
        text_path = Path(ocr_text_file)
        if not text_path.is_file():
            raise ValueError(f"OCR text file not found: {ocr_text_file}")
        return text_path.read_text(encoding="utf-8")
    return _default_ocr_text(image_path)


def _resolve_output_target(source: Path, output_path: str | None, output_format: str) -> Path:
    requested = "." + output_format.lower().lstrip(".")
    if requested not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ValueError(f"unsupported output format: {output_format}")
    if output_path:
        target = Path(output_path)
        if target.suffix.lower() not in SUPPORTED_OUTPUT_EXTENSIONS:
            raise ValueError(f"unsupported output extension: {target.suffix}")
        return target
    return source.with_suffix(requested)


def _default_ocr_text(image_path: Path) -> str:
    text = os.getenv("IMAGE_TABLE_OCR_TEXT")
    if text:
        return text
    if os.getenv("IMAGE_TABLE_VISION_BASE_URL") and os.getenv("IMAGE_TABLE_VISION_MODEL"):
        return _ocr_with_openai_compatible_vision(image_path)
    raise RuntimeError(
        "OCR backend unavailable: inject ocr_backend, pass --ocr-text-file, set IMAGE_TABLE_OCR_TEXT, "
        "or configure IMAGE_TABLE_VISION_BASE_URL and IMAGE_TABLE_VISION_MODEL"
    )


def _ocr_with_openai_compatible_vision(image_path: Path) -> str:
    payload = {
        "model": os.environ["IMAGE_TABLE_VISION_MODEL"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract the visible estimate table from this image. Return plain text only, "
                            "one row per line, preserving item name, unit, price, quantity and total. "
                            "Do not add explanations or markdown."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
                ],
            }
        ],
        "temperature": 0,
    }
    request = urllib.request.Request(
        _chat_url(os.environ["IMAGE_TABLE_VISION_BASE_URL"]),
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"vision OCR backend call failed: {exc}") from exc
    try:
        return str(body["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("vision OCR backend returned unsupported response shape") from exc


def _data_url(image_path: Path) -> str:
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _chat_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("IMAGE_TABLE_VISION_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _validate_image_path(path: str) -> Path:
    image_path = Path(path)
    if not image_path.is_file():
        raise ValueError(f"image file not found: {path}")
    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported image extension: {image_path.suffix}")
    return image_path


def _is_header(line: str) -> bool:
    lowered = line.lower()
    return "цена" in lowered and ("кол-во" in lowered or "количество" in lowered)


def _is_number(value: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?", value.replace(" ", "")))


def _parse_number(value: str) -> float:
    return float(value.replace(" ", "").replace(",", "."))


def _number_or_blank(value: float | None) -> float | str:
    return "" if value is None else value


def _html_row(values: list[object]) -> str:
    return "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>"


def _content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""


def _root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _workbook() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Table" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""


def _workbook_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""


def _sheet_xml(table: list[list[object]]) -> str:
    rows = []
    for row_index, values in enumerate(table, start=1):
        cells = []
        for column_index, value in enumerate(values, start=1):
            ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        rows.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(rows) + "</sheetData></worksheet>"
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
'''


def _cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import argparse\n"
        "import sys\n\n"
        "from image_table_excel.table_extractor import image_table_to_excel\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser(description='Convert an image table to an Excel .xlsx workbook')\n"
        "    parser.add_argument('input')\n"
        "    parser.add_argument('output', nargs='?')\n"
        "    parser.add_argument('--format', choices=['xlsx', 'csv', 'xls', 'html', 'doc', 'rtf'], default='xlsx', help='Output format when output path is omitted')\n"
        "    parser.add_argument('--ocr-text-file', help='Read already recognized table text from UTF-8 file')\n"
        "    args = parser.parse_args(argv)\n"
        "    try:\n"
        "        result = image_table_to_excel(args.input, args.output, ocr_text_file=args.ocr_text_file, output_format=args.format)\n"
        "    except (RuntimeError, ValueError) as exc:\n"
        "        print(str(exc), file=sys.stderr)\n"
        "        return 2\n"
        "    print(result['output_path'])\n"
        "    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _root_cli() -> str:
    return (
        "from __future__ import annotations\n\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))\n\n"
        "from image_table_excel.cli import main\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _test_core() -> str:
    return r'''import zipfile
from pathlib import Path

import pytest

from image_table_excel.table_extractor import image_table_to_excel, parse_table_text


SAMPLE_OCR = """
Профлист шт 810 44 35 640,00
Проф труба 60x60x2 6м м 1300 9 11700
Краска, растворитель 2886
Итого 79415
"""


def test_parse_table_text_extracts_rows_and_numbers():
    rows = parse_table_text(SAMPLE_OCR)
    assert rows[0].name == "Профлист"
    assert rows[0].unit == "шт"
    assert rows[0].price == 810
    assert rows[0].quantity == 44
    assert rows[0].total == 35640
    assert rows[-1].name == "Итого"
    assert rows[-1].total == 79415


def test_image_table_to_excel_writes_same_stem_by_default(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR)
    output = Path(result["output_path"])
    assert output == tmp_path / "estimate.xlsx"
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Профлист" in sheet
    assert "79415.0" in sheet


def test_image_table_to_excel_accepts_ocr_text_file(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    text_file = tmp_path / "recognized.txt"
    text_file.write_text(SAMPLE_OCR, encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_text_file=str(text_file))
    assert Path(result["output_path"]).is_file()


def test_image_table_to_excel_writes_csv_when_requested(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR, output_format="csv")
    output = Path(result["output_path"])
    assert output == tmp_path / "estimate.csv"
    assert "Профлист" in output.read_text(encoding="utf-8-sig")


def test_image_table_to_excel_writes_xls_html_when_requested(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR, output_format="xls")
    output = Path(result["output_path"])
    assert output == tmp_path / "estimate.xls"
    text = output.read_text(encoding="utf-8")
    assert "<table>" in text
    assert "Профлист" in text


def test_image_table_to_excel_writes_html_when_requested(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR, output_format="html")
    output = Path(result["output_path"])
    assert output == tmp_path / "estimate.html"
    text = output.read_text(encoding="utf-8")
    assert "<table>" in text
    assert "Профлист" in text


def test_image_table_to_excel_writes_doc_html_when_requested(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR, output_format="doc")
    output = Path(result["output_path"])
    assert output == tmp_path / "estimate.doc"
    text = output.read_text(encoding="utf-8")
    assert "<table>" in text
    assert "Профлист" in text


def test_image_table_to_excel_writes_rtf_when_requested(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    result = image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR, output_format="rtf")
    output = Path(result["output_path"])
    assert output == tmp_path / "estimate.rtf"
    text = output.read_text(encoding="utf-8")
    assert text.startswith("{\\rtf1")
    assert "Профлист" in text


def test_missing_image_is_rejected():
    with pytest.raises(ValueError, match="image file not found"):
        image_table_to_excel("tests/fixtures/missing.webp", ocr_backend=lambda path: SAMPLE_OCR)


def test_missing_ocr_backend_is_controlled():
    with pytest.raises(RuntimeError, match="OCR backend unavailable"):
        image_table_to_excel("tests/fixtures/sample.webp")


def test_missing_ocr_text_file_is_rejected(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="OCR text file not found"):
        image_table_to_excel(str(image), ocr_text_file=str(tmp_path / "missing.txt"))


def test_unsupported_output_format_is_rejected(tmp_path):
    image = tmp_path / "estimate.webp"
    image.write_text("fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported output format"):
        image_table_to_excel(str(image), ocr_backend=lambda path: SAMPLE_OCR, output_format="pdf")
'''


def _test_cli() -> str:
    return (
        "from pathlib import Path\n\n"
        "from image_table_excel import cli\n\n\n"
        "def test_cli_writes_workbook(monkeypatch, tmp_path, capsys):\n"
        "    def fake_convert(image_path, output_path=None, ocr_text_file=None, output_format='xlsx'):\n"
        "        target = Path(output_path) if output_path else Path(image_path).with_suffix('.xlsx')\n"
        "        target.write_text('xlsx fixture', encoding='utf-8')\n"
        "        return {'input_path': image_path, 'output_path': str(target), 'rows': 1}\n\n"
        "    image = tmp_path / 'table.webp'\n"
        "    image.write_text('fixture', encoding='utf-8')\n"
        "    monkeypatch.setattr(cli, 'image_table_to_excel', fake_convert)\n"
        "    assert cli.main([str(image)]) == 0\n"
        "    assert str(image.with_suffix('.xlsx')) in capsys.readouterr().out\n\n\n"
        "def test_cli_reports_controlled_error(monkeypatch, capsys):\n"
        "    def fail(image_path, output_path=None, ocr_text_file=None, output_format='xlsx'):\n"
        "        raise RuntimeError('OCR backend unavailable')\n\n"
        "    monkeypatch.setattr(cli, 'image_table_to_excel', fail)\n"
        "    assert cli.main(['tests/fixtures/sample.webp']) == 2\n"
        "    assert 'OCR backend unavailable' in capsys.readouterr().err\n"
        "\n\n"
        "def test_cli_forwards_ocr_text_file(monkeypatch, tmp_path):\n"
        "    captured = {}\n\n"
        "    def fake_convert(image_path, output_path=None, ocr_text_file=None, output_format='xlsx'):\n"
        "        captured['ocr_text_file'] = ocr_text_file\n"
        "        target = Path(image_path).with_suffix('.xlsx')\n"
        "        target.write_text('xlsx fixture', encoding='utf-8')\n"
        "        return {'input_path': image_path, 'output_path': str(target), 'rows': 1}\n\n"
        "    image = tmp_path / 'table.webp'\n"
        "    text = tmp_path / 'recognized.txt'\n"
        "    image.write_text('fixture', encoding='utf-8')\n"
        "    text.write_text('row', encoding='utf-8')\n"
        "    monkeypatch.setattr(cli, 'image_table_to_excel', fake_convert)\n"
        "    assert cli.main([str(image), '--ocr-text-file', str(text)]) == 0\n"
        "    assert captured['ocr_text_file'] == str(text)\n"
        "\n\n"
        "def test_cli_forwards_output_format(monkeypatch, tmp_path):\n"
        "    captured = {}\n\n"
        "    def fake_convert(image_path, output_path=None, ocr_text_file=None, output_format='xlsx'):\n"
        "        captured['output_format'] = output_format\n"
        "        target = Path(image_path).with_suffix('.doc')\n"
        "        target.write_text('doc fixture', encoding='utf-8')\n"
        "        return {'input_path': image_path, 'output_path': str(target), 'rows': 1}\n\n"
        "    image = tmp_path / 'table.webp'\n"
        "    image.write_text('fixture', encoding='utf-8')\n"
        "    monkeypatch.setattr(cli, 'image_table_to_excel', fake_convert)\n"
        "    assert cli.main([str(image), '--format', 'doc']) == 0\n"
        "    assert captured['output_format'] == 'doc'\n"
    )
