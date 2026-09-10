from pathlib import Path

from runtime.executable_acceptance_support import callable_target_support


def test_isolated_execution_failure_supersedes_import_fallback(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "module.py").write_text(
        "raise RuntimeError('import side effect')\n\n"
        "def explode(value):\n    raise ValueError('sample failure')\n\n"
        "def parse(value):\n    return explode(value)\n",
        encoding="utf-8",
    )
    target = "pkg/module.py:parse"
    obligations = [
        {
            "target": target,
            "kind": "positive_contract_case",
            "given": {"value": "sample"},
            "expect": {"result": "str"},
        }
    ]

    result = callable_target_support(project, target, obligations)

    assert result["reason"] == "positive_sample_execution_failed"
    assert result["detail"] == "ValueError: sample failure"
