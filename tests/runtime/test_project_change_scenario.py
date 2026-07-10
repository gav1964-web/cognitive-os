import subprocess
import sys
from pathlib import Path

from runtime.project_change_scenario import run_project_change_scenario


SCENARIO = Path("benchmarks/project_change_trials/direct_provider_probe/scenario.json")


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
