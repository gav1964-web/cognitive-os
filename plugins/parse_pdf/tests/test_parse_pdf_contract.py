from pathlib import Path
import importlib.util


def _run(payload: dict[str, object]) -> dict[str, object]:
    module_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("parse_pdf_main_contract", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(payload)


def test_candidate_contract(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    result = _run({"path": "tests/fixtures/sample.pdf"})
    assert result["text"] == "Hello PDF Field Trial"
    assert result["page_count"] == 1
    assert result["backend"] in {"builtin", "pypdf"}
