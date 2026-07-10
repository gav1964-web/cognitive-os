import subprocess
import sys
from pathlib import Path

import pytest

from runtime.project_change_scenario import run_project_change_scenario, validate_project_change_scenario


SCENARIO = Path("benchmarks/project_change_trials/direct_provider_probe/scenario.json")
PATCH_SCENARIO = Path("benchmarks/project_change_trials/gigachat_patch_package_probe/scenario.json")


def test_project_change_scenario_runs_declarative_fixture(tmp_path: Path) -> None:
    report = run_project_change_scenario(root=tmp_path, scenario_path=SCENARIO, write=True)

    assert report["status"] == "ok"
    assert report["scenario"]["id"] == "direct_provider_probe"
    assert report["comparison"]["exact_match"] is True
    assert report["comparison"]["feature_score"] == report["comparison"]["feature_total"]
    assert report["simulated_apply"]["target"] == "fixture"
    assert report["invariants"]["source_project_modified"] is False
    assert Path(report["report_path"]).is_file()


def test_project_change_scenario_cli(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/project_change_trial_run.py",
            "--root",
            str(tmp_path),
            "--scenario",
            str(SCENARIO),
            "--write",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0
    assert '"status": "ok"' in result.stdout


def test_project_change_scenario_runs_sandbox_patch_package(tmp_path: Path) -> None:
    report = run_project_change_scenario(root=tmp_path, scenario_path=PATCH_SCENARIO, write=True)

    assert report["status"] == "ok"
    assert report["scenario"]["apply_type"] == "sandbox_patch_package"
    assert report["apply_result"]["package"]["status"] == "ok"
    assert report["apply_result"]["package"]["verification"] == "passed"
    assert report["apply_result"]["review"]["status"] == "applied"
    assert report["comparison"]["exact_match"] is False
    assert report["comparison"]["exact_match_required"] is False
    assert report["comparison"]["feature_score"] == report["comparison"]["feature_total"]
    assert report["invariants"]["fixture_only_apply"] is True


def test_project_change_scenario_validation_rejects_unsafe_target() -> None:
    scenario = {
        "id": "bad",
        "source_project": "benchmarks/project_change_trials/direct_provider_probe/source_project",
        "teacher_reference": {"file": "benchmarks/project_change_trials/direct_provider_probe/source_project/client.py"},
        "files": [
            {
                "target_relative": "../client.py",
                "baseline": "benchmarks/project_change_trials/direct_provider_probe/source_project/client.py.bak.0",
            }
        ],
    }

    validation = validate_project_change_scenario(scenario=scenario, base_dir=Path("."))

    assert validation["status"] == "failed"
    assert any("safe relative path" in error for error in validation["errors"])


def test_project_change_scenario_rejects_unsupported_apply(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.json"
    source_project = tmp_path / "source"
    source_project.mkdir()
    (source_project / "client.py").write_text("MODEL = 'teacher'\n", encoding="utf-8")
    (source_project / "client.py.bak.0").write_text("MODEL = 'baseline'\n", encoding="utf-8")
    scenario_path.write_text(
        """{
  "id": "bad_apply",
  "source_project": "source",
  "teacher_reference": {"file": "source/client.py"},
  "files": [{"target_relative": "client.py", "baseline": "source/client.py.bak.0"}],
  "apply": {"type": "shell_command"}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported scenario apply type"):
        run_project_change_scenario(root=tmp_path, scenario_path=scenario_path)


def test_project_change_scenario_rejects_unsupported_patch_builder() -> None:
    scenario = {
        "id": "bad_builder",
        "source_project": "benchmarks/project_change_trials/gigachat_patch_package_probe/source_project",
        "teacher_reference": {"file": "benchmarks/project_change_trials/gigachat_patch_package_probe/source_project/import_indoc.py"},
        "files": [
            {
                "target_relative": "import_indoc.py",
                "baseline": "benchmarks/project_change_trials/gigachat_patch_package_probe/source_project/import_indoc.py.bak.0",
            }
        ],
        "apply": {"type": "sandbox_patch_package", "builder": "shell"},
    }

    validation = validate_project_change_scenario(scenario=scenario, base_dir=Path("."))

    assert validation["status"] == "failed"
    assert any("unsupported sandbox patch builder" in error for error in validation["errors"])


def test_project_change_scenario_cli_reports_validation_error(tmp_path: Path) -> None:
    scenario_path = tmp_path / "missing_fields.json"
    scenario_path.write_text('{"id": "bad"}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/project_change_trial_run.py",
            "--root",
            str(tmp_path),
            "--scenario",
            str(scenario_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 1
    assert '"status": "failed"' in result.stdout
    assert "files must be a non-empty list" in result.stdout


def test_project_change_scenario_validation_rejects_non_object() -> None:
    validation = validate_project_change_scenario(scenario=[], base_dir=Path("."))  # type: ignore[arg-type]

    assert validation == {"status": "failed", "errors": ["scenario must be an object"]}
