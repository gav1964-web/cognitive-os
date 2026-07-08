from pathlib import Path
import importlib.util

import pytest


def _run(payload: dict[str, object]) -> dict[str, object]:
    module_path = Path(__file__).resolve().parents[1] / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("translate_text_main_negative", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(payload)


def test_candidate_rejects_missing_value():
    with pytest.raises(KeyError):
        _run({})


def test_candidate_rejects_unsupported_language():
    with pytest.raises(ValueError):
        _run({"text": "hello", "target_language": "French"})
