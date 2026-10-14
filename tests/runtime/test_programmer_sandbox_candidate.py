from __future__ import annotations

from pathlib import Path

from runtime.programmer_sandbox_candidate import apply_sandbox_patch_candidate


def test_sandbox_candidate_applies_unified_diff_without_source_changes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 'old'\n", encoding="utf-8")
    strategy = {
        "sandbox_patch_candidate": {"status": "candidate_ready_for_sandbox_attempt"},
        "llm_strategy": {
            "patch_recipe_hypothesis": {
                "recipe_type": "replace_literal",
                "diff": [
                    "--- a/main.py",
                    "+++ b/main.py",
                    "@@ -1,2 +1,2 @@",
                    " def run():",
                    "-    return 'old'",
                    "+    return 'new'",
                ],
            }
        },
    }

    result = apply_sandbox_patch_candidate(
        execution_dir=tmp_path / "exec",
        project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": "main.py:run"},
            "patch_intent": {"target_symbol": "main.py:run"},
            "expected_files": ["main.py"],
        },
        strategy=strategy,
    )

    sandbox_file = Path(result["sandbox_project"]) / "main.py"
    assert result["status"] == "applied_in_sandbox"
    assert "return 'new'" in sandbox_file.read_text(encoding="utf-8")
    assert "return 'old'" in (project / "main.py").read_text(encoding="utf-8")


def test_sandbox_candidate_blocks_non_matching_diff(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 'old'\n", encoding="utf-8")

    result = apply_sandbox_patch_candidate(
        execution_dir=tmp_path / "exec",
        project_dir=project,
        implementation_plan={"implementation_target": {"candidate": "main.py:run"}, "expected_files": ["main.py"]},
        strategy={
            "sandbox_patch_candidate": {"status": "candidate_ready_for_sandbox_attempt"},
            "llm_strategy": {"patch_recipe_hypothesis": {"diff": ["@@ -1,2 +1,2 @@", " def run():", "-    missing"]}},
        },
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "diff_apply_failed"


def test_sandbox_candidate_applies_structured_batch_across_expected_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 'old'\n", encoding="utf-8")
    (project / "helper.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    strategy = _batch_strategy(
        [
            {"target_symbol": "main.py:run", "replacement_source": "def run():\n    return 'new'"},
            {"target_symbol": "helper.py:value", "replacement_source": "def value():\n    return 2"},
        ]
    )

    result = apply_sandbox_patch_candidate(
        execution_dir=tmp_path / "exec",
        project_dir=project,
        implementation_plan=_batch_plan(),
        strategy=strategy,
    )

    sandbox = Path(result["sandbox_project"])
    assert result["status"] == "applied_in_sandbox"
    assert result["reason"] == "structured_function_batch_applied"
    assert len(result["patches"]) == 2
    assert "return 'new'" in (sandbox / "main.py").read_text(encoding="utf-8")
    assert "return 2" in (sandbox / "helper.py").read_text(encoding="utf-8")
    assert "return 'old'" in (project / "main.py").read_text(encoding="utf-8")


def test_sandbox_candidate_does_not_partially_write_failed_batch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    original = "def run():\n    return 'old'\n"
    (project / "main.py").write_text(original, encoding="utf-8")
    (project / "helper.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    strategy = _batch_strategy(
        [
            {"target_symbol": "main.py:run", "replacement_source": "def run():\n    return 'new'"},
            {"target_symbol": "helper.py:missing", "replacement_source": "def missing():\n    return 2"},
        ]
    )

    result = apply_sandbox_patch_candidate(
        execution_dir=tmp_path / "exec",
        project_dir=project,
        implementation_plan=_batch_plan(),
        strategy=strategy,
    )

    sandbox = Path(result["sandbox_project"])
    assert result["status"] == "blocked"
    assert result["reason"] == "structured_target_not_unique"
    assert (sandbox / "main.py").read_text(encoding="utf-8") == original


def test_sandbox_candidate_blocks_batch_target_outside_change_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 1\n\ndef hidden():\n    return 1\n", encoding="utf-8")
    plan = _batch_plan()
    strategy = _batch_strategy(
        [{"target_symbol": "main.py:hidden", "replacement_source": "def hidden():\n    return 2"}]
    )

    result = apply_sandbox_patch_candidate(
        execution_dir=tmp_path / "exec",
        project_dir=project,
        implementation_plan=plan,
        strategy=strategy,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "edit_target_outside_plan"


def test_single_repair_candidate_can_target_secondary_planned_function(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def primary():\n    return 1\n\ndef secondary():\n    return 1\n", encoding="utf-8"
    )
    result = apply_sandbox_patch_candidate(
        execution_dir=tmp_path / "exec",
        project_dir=project,
        implementation_plan={
            "patch_intent": {"target_symbol": "main.py:primary"},
            "expected_files": ["main.py"],
            "change_plan": [{"target": "main.py:primary"}, {"target": "main.py:secondary"}],
        },
        strategy={
            "sandbox_patch_candidate": {
                "status": "candidate_ready_for_sandbox_attempt",
                "target": "main.py:secondary",
            },
            "llm_strategy": {
                "patch_recipe_hypothesis": {
                    "recipe_type": "repair",
                    "target_symbol": "main.py:secondary",
                    "replacement_source": "def secondary():\n    return 2",
                }
            },
        },
    )

    sandbox = Path(result["sandbox_project"])
    assert result["status"] == "applied_in_sandbox"
    assert "def primary():\n    return 1" in (sandbox / "main.py").read_text(encoding="utf-8")
    assert "def secondary():\n    return 2" in (sandbox / "main.py").read_text(encoding="utf-8")


def _batch_plan() -> dict:
    return {
        "patch_intent": {"target_symbol": "main.py:run"},
        "expected_files": ["main.py", "helper.py"],
        "change_plan": [
            {"target": "main.py:run"},
            {"target": "helper.py:value"},
            {"target": "helper.py:missing"},
        ],
    }


def _batch_strategy(edits: list[dict]) -> dict:
    return {
        "sandbox_patch_candidate": {"status": "candidate_ready_for_sandbox_attempt"},
        "llm_strategy": {
            "patch_recipe_hypothesis": {
                "recipe_type": "composite",
                "target_symbol": "main.py:run",
                "edits": edits,
            }
        },
    }
