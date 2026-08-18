from __future__ import annotations

from pathlib import Path

from runtime.programmer_executor import _repair_needed
from runtime.programmer_patch_strategy import _patch_recipe_hypothesis
from runtime.programmer_repair_strategy import _normalize
from runtime.programmer_source_location import source_location


def test_source_location_includes_full_file_line_and_nearby_globals(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "COMMANDS = {'run'}\n\ndef resolve(value):\n    return value\n",
        encoding="utf-8",
    )

    location = source_location(project, "main.py:resolve")

    assert location["start_line"] == 3
    assert location["excerpt"] == "def resolve(value):\n    return value"
    assert "COMMANDS = {'run'}" in location["context"]
    assert location["context_start_line"] == 1


def test_llm_diff_normalizers_accept_newline_delimited_string():
    diff = "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new"
    payload = {
        "action": "propose_patch_recipe",
        "patch_recipe_hypothesis": {
            "recipe_type": "replace",
            "target_symbol": "main.py:run",
            "diff": diff,
        },
    }

    assert _patch_recipe_hypothesis(payload)["diff"] == diff.splitlines()
    assert _normalize(payload)["patch_recipe_hypothesis"]["diff"] == diff.splitlines()


def test_executor_repairs_only_safe_diff_application_failures(monkeypatch):
    monkeypatch.setenv("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", "1")

    assert _repair_needed({}, {"status": "blocked", "reason": "diff_apply_failed"}) is True
    assert _repair_needed({}, {"status": "blocked", "reason": "target_outside_sandbox"}) is False
    assert _repair_needed({}, {"status": "not_applied", "reason": "blocked_invalid_candidate"}) is False
