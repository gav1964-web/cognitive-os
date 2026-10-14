from __future__ import annotations

from tests.runtime.executable_acceptance_contract_inference_helpers import *

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


def test_executable_acceptance_materializes_upstream_local_model_recipe(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(project, "def greet(request):\n    return request.name.upper()\n")
    (project / "test_greet.py").write_text(
        "def test_greet():\n    assert greet(CreateRequest(name='Ada')) == 'ADA'\n", encoding="utf-8"
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:greet", {"request": "sample"}, malformed=False),
        work_dir=tmp_path / "work-model",
    )

    assert result["status"] == "passed"
    evidence = result["summary"]["argument_sample_evidence"]["module.py:greet"]["request"]
    assert evidence["source"] == "upstream_test_call:constructor"
    assert evidence["value"]["fields"] == {"name": "Ada"}


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


def test_dynamic_isinstance_type_parameter_keeps_value_and_type_samples_coherent(tmp_path: Path):
    path = tmp_path / "validate.py"
    path.write_text(
        "def validate(val, of_type):\n"
        "    if hasattr(val, 'values'):\n"
        "        list(val.values())\n"
        "    if not isinstance(val, of_type):\n"
        "        raise TypeError\n"
        "    return val\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "validate")["val"] == {
        "value": "sample",
        "source": "ast_dynamic_type_check:of_type",
    }
