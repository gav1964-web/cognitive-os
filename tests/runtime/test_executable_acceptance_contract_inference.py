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


def test_infers_anonymized_literal_from_upstream_test_call(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def parse(value):\n    return float(value)\n")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_parse.py").write_text(
        "def test_parse():\n    assert parse('2.5') == 2.5\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "2.5", "source": "upstream_test_call:literal"}
    }


def test_ignores_same_named_attribute_call_from_unrelated_object(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def parse(value):\n    return float(value)\n")
    (project / "test_other.py").write_text(
        "def test_other(parser):\n    assert parser.parse('wrong')\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "1.0", "source": "ast_conversion:float"}
    }


def test_accepts_qualified_call_only_when_import_points_to_target_module(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    path = package / "parser.py"
    path.write_text("def parse(value):\n    return float(value)\n", encoding="utf-8")
    (project / "test_parser.py").write_text(
        "from pkg import parser\n\ndef test_parse():\n    assert parser.parse('3.5') == 3.5\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "3.5", "source": "upstream_test_call:literal"}
    }


def test_preserves_none_literal_from_upstream_optional_call(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def normalize(value):\n    return value or 'default'\n")
    (project / "test_normalize.py").write_text(
        "def test_normalize():\n    assert normalize(None) == 'default'\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "normalize", project_root=project) == {
        "value": {"value": None, "source": "upstream_test_call:literal"}
    }


def test_rejects_upstream_factory_expression(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = _source(project, "def parse(value):\n    return float(value)\n")
    (project / "test_parse.py").write_text(
        "def test_parse():\n    assert parse(make_value()) == 1.0\n", encoding="utf-8"
    )

    assert infer_argument_samples(path, "parse", project_root=project) == {
        "value": {"value": "1.0", "source": "ast_conversion:float"}
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
