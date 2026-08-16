import sys
import json
from pathlib import Path

from runtime.executable_acceptance_environment import environment_harness_summary
from runtime.executable_acceptance_runner import run_acceptance_command


def test_stdlib_runner_executes_generated_acceptance_without_pytest(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_path = tests_dir / "test_generated.py"
    test_path.write_text(
        "def test_generated_contract():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )

    result = run_acceptance_command(
        python_executable=Path(sys.executable),
        tests_dir=tests_dir,
        test_path=test_path,
        cwd=tmp_path,
    )

    assert result["status"] == "passed"
    assert result["runner"] == "stdlib"
    assert result["python"] == Path(sys.executable).resolve().as_posix()


def test_environment_harness_uses_approved_python(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def normalize(value: str) -> str:\n    return value.strip()\n",
        encoding="utf-8",
    )
    obligations = tmp_path / "obligations.json"
    obligations.write_text(json.dumps([
        {
            "target": "main.py:normalize",
            "kind": "positive_contract_case",
            "given": {"value": " sample "},
            "expect": {"result": "string"},
        },
        {
            "target": "main.py:normalize",
            "kind": "malformed_input_case",
            "given": {},
            "expect": {"error": "controlled_validation_error"},
        },
    ]), encoding="utf-8")

    summary = environment_harness_summary(
        root=Path(__file__).resolve().parents[2],
        project_dir=project,
        obligations_path=obligations,
        python_executable=Path(sys.executable),
    )

    assert summary["environment_probe"]["status"] == "passed"
    assert summary["callable_harness_count"] == 1
    assert summary["signal_strength"] == "executable_callable"
