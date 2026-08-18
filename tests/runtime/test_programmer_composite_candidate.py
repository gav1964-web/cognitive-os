from __future__ import annotations

from pathlib import Path

from runtime.programmer_patch_strategy import build_patch_strategy


def test_patch_strategy_builds_valid_composite_candidate_from_change_plan(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (project / "helper.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    captured = {}

    def fake_llm(messages, config=None):
        captured["messages"] = messages
        return {
            "action": "propose_patch_recipe",
            "patch_recipe_hypothesis": {
                "recipe_type": "composite_contract_change",
                "target_symbol": "main.py:run",
                "edit_format": "replace_functions",
                "edits": [
                    {"target_symbol": "main.py:run", "replacement_source": "def run():\n    return 2"},
                    {"target_symbol": "helper.py:value", "replacement_source": "def value():\n    return 2"},
                ],
            },
        }

    monkeypatch.setattr("runtime.programmer_patch_strategy.call_json_chat", fake_llm)
    proposal = build_patch_strategy(
        project_dir=project,
        technical_spec={},
        implementation_plan={
            "implementation_target": {"candidate": "main.py:run"},
            "patch_intent": {"target_symbol": "main.py:run"},
            "expected_files": ["main.py", "helper.py"],
            "change_plan": [{"target": "main.py:run"}, {"target": "helper.py:value"}],
        },
        test_plan={},
        synthesis={"status": "skipped", "reason": "no_deterministic_patch_recipe"},
        use_l45_llm=True,
    )

    candidate = proposal["sandbox_patch_candidate"]
    assert candidate["status"] == "candidate_ready_for_sandbox_attempt"
    assert candidate["edit_count"] == 2
    assert "replace_functions" in captured["messages"][0]["content"]
    assert "helper.py:value" in captured["messages"][1]["content"]
