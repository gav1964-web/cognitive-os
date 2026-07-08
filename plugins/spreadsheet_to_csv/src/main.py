"""Convert a scoped .xlsx worksheet to CSV."""

from __future__ import annotations

import csv
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def run(payload: dict[str, object]) -> dict[str, object]:
    input_path = _scoped_path(payload["input_path"])
    output_path = _scoped_path(payload["output_path"])
    sheet_name = str(payload.get("sheet") or "")
    if input_path.suffix.lower() == ".xls":
        raise ValueError(".xls is a legacy binary format and requires an optional xlrd backend")
    if input_path.suffix.lower() != ".xlsx":
        raise ValueError("spreadsheet_to_csv supports .xlsx input")
    rows = _read_xlsx(input_path, sheet_name or None)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return {"path": output_path.as_posix(), "rows": len(rows), "columns": max((len(row) for row in rows), default=0)}


def _read_xlsx(path: Path, sheet_name: str | None) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheet_path = _sheet_path(archive, sheet_name)
        root = ET.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//main:sheetData/main:row", NS):
        values: list[str] = []
        for cell in row.findall("main:c", NS):
            index = _column_index(str(cell.get("r") or "")) or len(values) + 1
            while len(values) < index - 1:
                values.append("")
            values.append(_cell_value(cell, shared))
        rows.append(_trim(values))
    return rows


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str | None) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels.findall("pkg:Relationship", NS)}
    sheets = workbook.findall(".//main:sheets/main:sheet", NS)
    selected = next((s for s in sheets if sheet_name and s.get("name") == sheet_name), sheets[0] if sheets else None)
    if selected is None:
        raise ValueError("xlsx workbook has no worksheets")
    target = targets.get(selected.get(f"{{{NS['rel']}}}id"))
    if not target:
        raise ValueError("xlsx worksheet relationship is missing")
    return posixpath.normpath(posixpath.join("xl", target))


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall("main:si", NS):
        parts = [node.text or "" for node in item.findall(".//main:t", NS)]
        strings.append("".join(parts))
    return strings


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", NS))
    value = cell.findtext("main:v", default="", namespaces=NS)
    if kind == "s":
        return shared[int(value)] if value and int(value) < len(shared) else ""
    if kind == "b":
        return "TRUE" if value == "1" else "FALSE"
    return value


def _column_index(ref: str) -> int | None:
    match = re.match(r"([A-Z]+)", ref.upper())
    if not match:
        return None
    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - 64
    return index


def _trim(values: list[str]) -> list[str]:
    while values and values[-1] == "":
        values.pop()
    return values


def _scoped_path(value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("spreadsheet paths must be workspace-relative and scoped")
    return path
