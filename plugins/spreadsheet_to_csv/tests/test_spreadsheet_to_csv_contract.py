from pathlib import Path

import pytest

from plugins.csv_to_spreadsheet.src.main import run as csv_to_spreadsheet
from plugins.spreadsheet_to_csv.src.main import run


def test_spreadsheet_to_csv_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("input.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    csv_to_spreadsheet({"input_path": "input.csv", "output_path": "book.xlsx"})

    result = run({"input_path": "book.xlsx", "output_path": "out.csv"})

    assert result == {"path": "out.csv", "rows": 2, "columns": 2}
    assert Path("out.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_spreadsheet_to_csv_rejects_xls_without_optional_backend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("book.xls").write_bytes(b"not real xls")

    with pytest.raises(ValueError, match="legacy binary"):
        run({"input_path": "book.xls", "output_path": "out.csv"})
