from __future__ import annotations

import json
import re
import shutil
import subprocess
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime.interface_contracts import interface_contract_for_operation
from runtime.local_inference import LocalInferenceError, call_json_chat
from runtime.operation_recipe import recipe_from_operation, validate_operation_recipe
from runtime.operation_recipe_rules import load_operation_recipe_rules
from runtime.sandbox_operation_graph import build_sandbox_operation_graph
from runtime.sandbox_programmer_profiles import expression_policy, load_sandbox_programmer_profiles
from runtime.sandbox_release_policy import sandbox_implementation_policy

def _cli_py(operation: SandboxOperation) -> str:
    if operation.profile == "numeric_args_sum":
        return _numeric_args_cli_py()
    if operation.profile == "numeric_args_expression":
        return _numeric_args_expression_cli_py(operation)
    if operation.profile == "numeric_args_file_expression":
        return _numeric_args_file_expression_cli_py(operation)
    if operation.profile == "stdin_text_expression":
        return _stdin_stdout_cli_py(operation)
    if operation.profile == "stdin_file_text_expression":
        return _stdin_file_cli_py(operation)
    if operation.profile == "file_stdout_text_expression":
        return _file_stdout_cli_py(operation)
    body = _transform_body(operation)
    return f'''from __future__ import annotations

import argparse
import csv
from html.parser import HTMLParser
import io
import json
from pathlib import Path


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        if tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        if tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None


def transform(text: str) -> str:
{body}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    source = Path(args.input)
    if not source.is_file():
        parser.error(f"input file does not exist: {{source}}")
    Path(args.output).write_text(transform(source.read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

def _transform_body(operation: SandboxOperation) -> str:
    if operation.profile == "operation_composition":
        return _composition_transform_body(operation)
    if operation.profile == "text_expression":
        return f"    return {operation.expression}"
    if operation.profile == "line_sort":
        return '''    lines = text.splitlines()
    return "\\n".join(sorted(lines)) + ("\\n" if lines else "")'''
    if operation.profile == "line_unique":
        return '''    seen = set()
    result = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            result.append(line)
    return "\\n".join(result) + ("\\n" if result else "")'''
    if operation.profile == "csv_row_count":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "0\\n"
    data_rows = rows[1:] if rows and any(cell.strip() for cell in rows[0]) else rows
    return str(len([row for row in data_rows if any(cell.strip() for cell in row)])) + "\\n"'''
    if operation.profile == "csv_sort_first_column":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    header, data = rows[0], rows[1:]
    data = sorted(data, key=lambda row: row[0] if row else "")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerow(header)
    writer.writerows(data)
    return out.getvalue()'''
    if operation.profile == "csv_select_first_two_columns":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    for row in rows:
        writer.writerow(row[:2])
    return out.getvalue()'''
    if operation.profile == "csv_filter_first_column_nonempty":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    header, data = rows[0], rows[1:]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerow(header)
    writer.writerows([row for row in data if row and row[0].strip()])
    return out.getvalue()'''
    if operation.profile == "csv_sum_second_column":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    total = 0.0
    for row in rows[1:]:
        if len(row) > 1 and row[1].strip():
            total += float(row[1])
    if total.is_integer():
        return str(int(total)) + "\\n"
    return str(total) + "\\n"'''
    if operation.profile == "csv_to_json_records":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "[]\\n"
    header, data = rows[0], rows[1:]
    records = [dict(zip(header, row)) for row in data]
    return json.dumps(records, ensure_ascii=False, sort_keys=True) + "\\n"'''
    if operation.profile == "html_table_to_csv":
        return '''    parser = _TableParser()
    parser.feed(text)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerows(parser.rows)
    return out.getvalue()'''
    if operation.profile == "json_extract_first_key":
        return '''    payload = json.loads(text)
    if not isinstance(payload, dict) or not payload:
        return "\\n"
    key = sorted(payload)[0]
    return json.dumps(payload[key], ensure_ascii=False, sort_keys=True) + "\\n"'''
    if operation.profile == "json_keys":
        return '''    payload = json.loads(text)
    if not isinstance(payload, dict):
        return "[]\\n"
    return json.dumps(sorted(payload), ensure_ascii=False) + "\\n"'''
    if operation.profile == "json_pretty":
        return '''    payload = json.loads(text)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\\n"'''
    raise ValueError(f"unsupported operation profile: {operation.profile}")

def _composition_transform_body(operation: SandboxOperation) -> str:
    step_ids = [step.get("operation") for step in operation.steps or []]
    if step_ids == ["csv_filter_first_column_nonempty", "csv_select_first_two_columns", "csv_to_json_records"]:
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "[]\\n"
    header, data = rows[0], rows[1:]
    filtered = [row for row in data if row and row[0].strip()]
    selected_header = header[:2]
    selected_rows = [row[:2] for row in filtered]
    records = [dict(zip(selected_header, row)) for row in selected_rows]
    return json.dumps(records, ensure_ascii=False, sort_keys=True) + "\\n"'''
    if step_ids == ["trim", "upper"]:
        return '''    return text.strip().upper() + "\\n"'''
    raise ValueError(f"unsupported operation composition: {step_ids}")

def _test_py(operation: SandboxOperation) -> str:
    if operation.profile == "numeric_args_sum":
        return _numeric_args_test_py(operation)
    if operation.profile == "numeric_args_expression":
        return _numeric_args_expression_test_py(operation)
    if operation.profile == "numeric_args_file_expression":
        return _numeric_args_file_expression_test_py(operation)
    if operation.profile == "stdin_text_expression":
        return _stdin_stdout_test_py(operation)
    if operation.profile == "stdin_file_text_expression":
        return _stdin_file_test_py(operation)
    if operation.profile == "file_stdout_text_expression":
        return _file_stdout_test_py(operation)
    return f'''from pathlib import Path
import pytest

from {operation.package}.cli import main, transform


def test_transform_contract():
    assert transform({operation.sample!r}) == {operation.expected!r}


def test_cli_writes_output(tmp_path: Path):
    source = Path(__file__).parent / "fixtures" / "input.txt"
    expected = (Path(__file__).parent / "fixtures" / "expected.txt").read_text(encoding="utf-8")
    target = tmp_path / "out.txt"
    assert main([str(source), str(target)]) == 0
    assert target.read_text(encoding="utf-8") == expected


def test_cli_rejects_missing_input(tmp_path: Path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "missing.txt"), str(tmp_path / "out.txt")])
'''

def _numeric_args_cli_py() -> str:
    return '''from __future__ import annotations

import argparse


def parse_number(value: str) -> int | float:
    try:
        return int(value)
    except ValueError:
        return float(value)


def format_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def compute_sum(first: str, second: str) -> str:
    return format_number(parse_number(first) + parse_number(second)) + "\\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first")
    parser.add_argument("second")
    args = parser.parse_args(argv)
    try:
        print(compute_sum(args.first, args.second), end="")
    except ValueError as exc:
        parser.error(f"arguments must be numbers: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

def _numeric_args_test_py(operation: SandboxOperation) -> str:
    first, second = operation.sample.split()
    return f'''import pytest

from {operation.package}.cli import compute_sum, main


def test_compute_sum_contract():
    assert compute_sum({first!r}, {second!r}) == {operation.expected!r}


def test_main_prints_sum(capsys):
    assert main([{first!r}, {second!r}]) == 0
    assert capsys.readouterr().out == {operation.expected!r}


def test_main_rejects_non_numeric_argument():
    with pytest.raises(SystemExit):
        main(["one", "2"])
'''
