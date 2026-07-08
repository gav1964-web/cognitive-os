from pathlib import Path
import importlib.util


def _run(payload: dict[str, object]) -> dict[str, object]:
    module_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("translate_text_main_contract", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(payload)


def test_candidate_contract():
    assert _run({"text": "hello", "target_language": "German"}) == {"text": "hallo", "language": "German"}


def test_candidate_accepts_language_alias():
    assert _run({"text": "thank you", "target_language": "de"}) == {"text": "danke", "language": "German"}
