from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from tests.runtime.test_executable_acceptance import _plan


def _run(tmp_path: Path, source: str, target: str):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(source, encoding="utf-8")
    return run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan(target, {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )


def test_executes_qualified_classmethod_target(tmp_path: Path):
    result = _run(
        tmp_path,
        "class Parser:\n    @classmethod\n    def from_cli(cls, value: str) -> str:\n        return value.strip()\n",
        "main.py:Parser.from_cli",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_infers_required_mapping_for_method_sample(tmp_path: Path):
    result = _run(
        tmp_path,
        "class Parser:\n    @staticmethod\n    def parse(value):\n        return {'parsed_url': value['url']}\n",
        "main.py:parse",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["main.py:parse"]
    assert evidence["value"]["source"] == "ast_required_mapping_keys"


def test_qualified_method_falls_back_when_class_decorator_replaces_class(tmp_path: Path):
    result = _run(
        tmp_path,
        "def public(value):\n    return lambda *args, **kwargs: None\n\n@public\nclass Parser:\n    def __init__(self, value):\n        self.value = value\n    @classmethod\n    def from_cli(cls, value):\n        return cls(value)\n",
        "main.py:Parser.from_cli",
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["main.py:Parser.from_cli"]
