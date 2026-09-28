from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _task(root: Path, name: str, prompt: str) -> None:
    task = root / "evaluation" / name
    (task / "direct_agent").mkdir(parents=True)
    (task / "cognitive_os").mkdir()
    (task / "prompt.md").write_text(f"# {name}\n\n## Prompt\n\n{prompt}\n\n## Success Criteria\n\n- ok\n", encoding="utf-8")
    route = {
        "executor": "not_run",
        "model": "not_run",
        "status": "not_run",
        "requirement_coverage": 0.0,
        "missed_requirements": 0,
        "invented_requirements": 0,
        "tests_passed": 0,
        "tests_total": 0,
        "verification_status": "not_run",
        "repair_cycles": 0,
        "runtime_seconds": None,
        "estimated_cost": None,
        "artifact_completeness": 0.0,
        "source_safety_violations": 0,
        "review_blockers": 0,
        "human_correction_minutes": None,
    }
    metrics = {
        "task_id": name,
        "task_class": "cli_utility",
        "prompt_hash": "sha256:test",
        "routes": {"direct_agent": dict(route), "cognitive_os": {**route, "status": "completed", "tests_passed": 1}},
        "comparison": {"winner": "undecided", "cognitive_os_advantages": [], "direct_agent_advantages": [], "no_difference": [], "confidence": 0.0},
        "invariants": {
            "same_original_prompt": True,
            "same_constraints": True,
            "manual_corrections_recorded": False,
            "teacher_reference_is_ground_truth": False,
            "source_mutation_detected": False,
        },
        "verdict": "not_evaluated",
    }
    (task / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (task / "verdict.md").write_text("# Verdict\n", encoding="utf-8")
    (task / "direct_agent" / "README.md").write_text("# Direct\n", encoding="utf-8")
    (task / "cognitive_os" / "README.md").write_text("# Cognitive\n", encoding="utf-8")


def test_evaluation_run_direct_agent_updates_metrics(tmp_path: Path):
    _task(tmp_path, "task15_uppercase_cli", "Напиши CLI .py, которая переводит текстовый файл в верхний регистр.")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "evaluation_run_direct_agent.py"),
            "--root",
            str(tmp_path),
            "--write",
            "task15_uppercase_cli",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(completed.stdout)
    metrics = json.loads((tmp_path / "evaluation" / "task15_uppercase_cli" / "metrics.json").read_text(encoding="utf-8"))
    assert report["tasks"][0]["status"] == "completed"
    assert metrics["routes"]["direct_agent"]["status"] == "completed"
    assert metrics["routes"]["direct_agent"]["tests_passed"] == 1


def test_evaluation_run_direct_agent_handles_markdown_to_rtf(tmp_path: Path):
    _task(tmp_path, "task03_markdown_to_rtf_cli", "Напиши CLI-конвертер файлов `.md` в `.rtf`.")

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "evaluation_run_direct_agent.py"),
            "--root",
            str(tmp_path),
            "--write",
            "task03_markdown_to_rtf_cli",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    metrics = json.loads((tmp_path / "evaluation" / "task03_markdown_to_rtf_cli" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["routes"]["direct_agent"]["status"] == "completed"
    assert metrics["routes"]["direct_agent"]["tests_passed"] == 1
