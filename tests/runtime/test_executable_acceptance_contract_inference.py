from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_contract_inference import infer_argument_samples
from tests.runtime.test_executable_acceptance import _plan


def _source(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "module.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_infers_numeric_string_from_runtime_conversion(tmp_path: Path):
    path = _source(tmp_path, "def parse(value):\n    return float(value)\n")

    assert infer_argument_samples(path, "parse") == {
        "value": {"value": "1.0", "source": "ast_conversion:float"}
    }


def test_infers_numeric_value_from_literal_comparison(tmp_path: Path):
    path = _source(tmp_path, "def schedule(epoch):\n    return 1 if epoch < 6 else 2\n")

    assert infer_argument_samples(path, "schedule") == {
        "epoch": {"value": 5, "source": "ast_comparison_literal"}
    }


def test_infers_datetime_string_from_strptime_format(tmp_path: Path):
    path = _source(
        tmp_path,
        "import datetime\n\ndef parse(value):\n"
        "    return datetime.datetime.strptime(value, '%Y%m%d%H%M')\n",
    )

    assert infer_argument_samples(path, "parse") == {
        "value": {"value": "202402030405", "source": "ast_strptime_format"}
    }


def test_executable_acceptance_uses_inferred_sample_and_records_evidence(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(project, "def schedule(epoch):\n    return 1 if epoch < 6 else 2\n")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:schedule", {"epoch": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["argument_overrides"] == {"module.py:schedule": {"epoch": 5}}
    assert result["summary"]["argument_sample_evidence"] == {
        "module.py:schedule": {
            "epoch": {"value": 5, "source": "ast_comparison_literal"}
        }
    }


def test_import_error_falls_back_to_source_isolated_callable(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(
        project,
        "from typing import DefinitelyUnavailable\n\n"
        "def normalize(value):\n    return value.strip()\n",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:normalize", {"value": " sample "}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["source_isolated_targets"] == ["module.py:normalize"]
