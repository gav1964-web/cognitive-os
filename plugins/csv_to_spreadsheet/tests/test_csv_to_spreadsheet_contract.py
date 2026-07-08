from pathlib import Path

import pytest

from plugins.csv_to_spreadsheet.src.main import run
from plugins.spreadsheet_to_csv.src.main import run as spreadsheet_to_csv


def test_csv_to_xlsx_contract_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("input.csv").write_text('name,value,note\nAlice,42,"hello, world"\nБоб,,unicode\n', encoding="utf-8")

    created = run({"input_path": "input.csv", "output_path": "out/book.xlsx", "sheet": "Data"})
    converted = spreadsheet_to_csv({"input_path": "out/book.xlsx", "output_path": "roundtrip.csv", "sheet": "Data"})

    assert created == {"path": "out/book.xlsx", "rows": 3, "columns": 3}
    assert converted == {"path": "roundtrip.csv", "rows": 3, "columns": 3}
    assert Path("roundtrip.csv").read_text(encoding="utf-8") == 'name,value,note\nAlice,42,"hello, world"\nБоб,,unicode\n'


def test_csv_to_xls_reports_controlled_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("input.csv").write_text("a,b\n", encoding="utf-8")

    with pytest.raises(ValueError, match="legacy binary"):
        run({"input_path": "input.csv", "output_path": "out.xls"})
