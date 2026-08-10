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
