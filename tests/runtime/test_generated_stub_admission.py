from __future__ import annotations

from pathlib import Path

from runtime.generated_stub_admission import inspect_generated_function_stubs


def _inspect(tmp_path: Path, before: str, after: str):
    original = tmp_path / "original"
    sandbox = tmp_path / "sandbox"
    original.mkdir()
    sandbox.mkdir()
    (original / "service.py").write_text(before, encoding="utf-8")
    (sandbox / "service.py").write_text(after, encoding="utf-8")
    return inspect_generated_function_stubs(
        original_project=original,
        sandbox_project=sandbox,
        patch={"patches": [{"file": "service.py"}]},
    )


def test_blocks_new_pass_function(tmp_path: Path):
    result = _inspect(tmp_path, "VALUE = 1\n", "VALUE = 1\n\ndef pending():\n    pass\n")

    assert result["status"] == "blocked"
    assert result["violations"] == [{
        "file": "service.py",
        "qualified_name": "pending",
        "line": 3,
        "marker": "pass",
        "change": "new_function_stub",
    }]


def test_blocks_existing_function_replaced_with_not_implemented(tmp_path: Path):
    result = _inspect(
        tmp_path,
        "def run():\n    return 1\n",
        "def run():\n    raise NotImplementedError('later')\n",
    )

    assert result["status"] == "blocked"
    assert result["violations"][0]["change"] == "function_replaced_with_stub"
    assert result["violations"][0]["marker"] == "raise_not_implemented_error"


def test_allows_pre_existing_abstract_stub_and_real_new_function(tmp_path: Path):
    result = _inspect(
        tmp_path,
        "class Port:\n    def send(self):\n        ...\n",
        "class Port:\n    def send(self):\n        ...\n\ndef normalize(value):\n    return value.strip()\n",
    )

    assert result["status"] == "passed"
    assert result["violations"] == []


def test_blocks_docstring_only_placeholder_marker(tmp_path: Path):
    result = _inspect(
        tmp_path,
        "VALUE = 1\n",
        'async def pending():\n    """Implement later."""\n    return NotImplemented\n',
    )

    assert result["status"] == "blocked"
    assert result["violations"][0]["marker"] == "return_not_implemented"
