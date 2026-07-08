from pathlib import Path
import importlib.util

import pytest


def _run(payload: dict[str, object]) -> dict[str, object]:
    module_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("parse_pdf_main_negative", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(payload)


def test_candidate_rejects_missing_path():
    with pytest.raises(KeyError):
        _run({})


def test_candidate_rejects_unsafe_path():
    with pytest.raises(ValueError):
        _run({"path": "../secret.pdf"})


def test_candidate_rejects_missing_file(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    with pytest.raises(ValueError):
        _run({"path": "tests/fixtures/missing.pdf"})


def test_candidate_rejects_non_pdf(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    with pytest.raises(ValueError):
        _run({"path": "tests/fixtures/not_pdf.txt"})
