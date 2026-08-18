from __future__ import annotations

from pathlib import Path

from runtime.programmer_acceptance_gate import acceptance_covers_plan, enforce_prepared_patch_acceptance
from runtime.programmer_patch_strategy import build_patch_strategy
from runtime.programmer_repair_strategy import build_patch_repair_strategy
from tools.programmer_l45_composite_trial import _applied_targets


def test_patch_strategy_builds_valid_composite_candidate_from_change_plan(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (project / "helper.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    captured = {}
    calls = {"count": 0}

    def fake_llm(messages, config=None):
        calls["count"] += 1
        captured["messages"] = messages
        if calls["count"] == 1:
            return {"action": "block_for_review"}
        return {
            "action": "propose_patch_recipe",
            "patch_recipe_hypothesis": {
                "recipe_type": "composite_contract_change",
                "target_symbol": "composite:declared_changes",
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
    assert calls["count"] == 2
    assert "replace_functions" in captured["messages"][0]["content"]
    assert "helper.py:value" in captured["messages"][1]["content"]


def test_composite_acceptance_requires_every_change_target():
    plan = {
        "patch_intent": {"target_symbol": "main.py:run"},
        "change_plan": [{"target": "main.py:run"}, {"target": "helper.py:value"}],
    }

    assert acceptance_covers_plan(
        {"signal_strength": "executable_callable", "callable_targets": ["main.py:run"]}, plan
    ) is False
    assert acceptance_covers_plan(
        {
            "signal_strength": "executable_callable",
            "callable_targets": ["main.py:run", "helper.py:value"],
        },
        plan,
    ) is True


def test_prepared_patch_gate_distinguishes_coverage_from_non_callable():
    plan = {
        "patch_intent": {"target_symbol": "main.py:run"},
        "change_plan": [{"target": "main.py:run"}, {"target": "helper.py:value"}],
    }
    incomplete = {
        "status": "ok",
        "summary": {"failed": 0},
        "executable_acceptance_result": {
            "summary": {"signal_strength": "executable_callable", "callable_targets": ["main.py:run"]}
        },
    }
    enforce_prepared_patch_acceptance(incomplete, {"status": "prepared"}, plan)
    assert incomplete["summary"]["prepared_patch_acceptance_gate"] == "failed_incomplete_callable_coverage"

    non_callable = {
        "status": "ok",
        "summary": {"failed": 0},
        "executable_acceptance_result": {"summary": {"signal_strength": "static_only"}},
    }
    enforce_prepared_patch_acceptance(non_callable, {"status": "prepared"}, plan)
    assert non_callable["summary"]["prepared_patch_acceptance_gate"] == "failed_non_callable_acceptance"


def test_composite_metric_accumulates_targets_across_repairs():
    initial = {"llm_strategy": {"patch_recipe_hypothesis": {"edits": [
        {"target_symbol": "main.py:run"}, {"target_symbol": "helper.py:value"}
    ]}}}
    repair = {"llm_strategy": {"patch_recipe_hypothesis": {"edits": [
        {"target_symbol": "helper.py:value"}
    ]}}}
    patch = {
        "executor_repair_strategies": [repair],
        "sandbox_candidate_repair_attempts": [{"status": "applied_in_sandbox"}],
    }
    assert _applied_targets(patch, initial, {"status": "applied_in_sandbox"}) == {
        "main.py:run", "helper.py:value"
    }


def test_repair_strategy_preserves_composite_target_set(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (project / "helper.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    payload = {
        "action": "propose_patch_recipe",
        "patch_recipe_hypothesis": {
            "recipe_type": "composite_repair",
            "target_symbol": "composite:repair",
            "edit_format": "replace_functions",
            "edits": [
                {"target_symbol": "main.py:run", "replacement_source": "def run():\n    return 2"},
                {"target_symbol": "helper.py:value", "replacement_source": "def value():\n    return 2"},
            ],
        },
    }
    monkeypatch.setattr("runtime.programmer_repair_strategy.call_json_chat", lambda messages, config=None: payload)

    proposal = build_patch_repair_strategy(
        project_dir=project,
        implementation_plan={
            "patch_intent": {"target_symbol": "main.py:run"},
            "expected_files": ["main.py", "helper.py"],
            "change_plan": [{"target": "main.py:run"}, {"target": "helper.py:value"}],
        },
        test_plan={},
        test_result={"status": "failed"},
    )

    candidate = proposal["sandbox_patch_candidate"]
    assert candidate["status"] == "candidate_ready_for_sandbox_attempt"
    assert candidate["edit_count"] == 2


def test_repair_strategy_targets_only_failed_composite_function(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (project / "helper.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    payload = {
        "action": "propose_patch_recipe",
        "patch_recipe_hypothesis": {
            "recipe_type": "targeted_repair",
            "target_symbol": "helper.py:value",
            "edit_format": "replace_functions",
            "edits": [{"target_symbol": "helper.py:value", "replacement_source": "def value():\n    return 2"}],
        },
    }
    monkeypatch.setattr("runtime.programmer_repair_strategy.call_json_chat", lambda messages, config=None: payload)
    proposal = build_patch_repair_strategy(
        project_dir=project,
        implementation_plan={
            "patch_intent": {"target_symbol": "main.py:run"},
            "expected_files": ["main.py", "helper.py"],
            "change_plan": [{"target": "main.py:run"}, {"target": "helper.py:value"}],
        },
        test_plan={"executable_acceptance": {"obligations": [{"target": "helper.py:value"}]}},
        test_result={
            "status": "failed",
            "executable_acceptance_result": {
                "summary": {
                    "skipped_targets": [
                        {"target": "helper.py:value", "reason": "positive_sample_execution_failed"}
                    ]
                }
            },
        },
    )
    candidate = proposal["sandbox_patch_candidate"]
    assert candidate["status"] == "candidate_ready_for_sandbox_attempt"
    assert candidate["target"] == "helper.py:value"
    assert candidate["edit_count"] == 1
