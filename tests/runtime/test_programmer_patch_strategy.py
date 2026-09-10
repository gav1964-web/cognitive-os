from __future__ import annotations

import json
from pathlib import Path

from runtime.programmer_executor import run_programmer_executor
from runtime.programmer_patch_strategy import build_patch_strategy


def _executor_inputs() -> tuple[dict, dict, dict]:
    target = "main.py:normalize"
    spec = {"artifact_type": "TechnicalSpec", "role": "spec_writer"}
    plan = {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": target},
        "patch_intent": {"artifact_type": "PatchIntent", "mode": "sandbox_first", "target_symbol": target},
        "writable_scope": [target],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "artifact_type": "TestPlan",
        "role": "tester",
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": target,
                    "kind": "positive_contract_case",
                    "given": {"value": " Sample "},
                    "expect": {"result": "str"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": target,
                    "kind": "side_effect_scope_case",
                    "given": {},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        },
    }
    return spec, plan, test_plan


def test_programmer_executor_writes_advisory_patch_strategy(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value.strip()\n", encoding="utf-8")
    spec, plan, test_plan = _executor_inputs()

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    assert patch["patch_strategy"]["artifact_type"] == "PatchStrategyProposal"
    assert patch["patch_strategy"]["authority"] == "proposal_only_verifier_required"
    assert patch["patch_strategy"]["patch_quality"]["level"] == "signature_fallback_guard"
    assert patch["patch_strategy"]["patch_quality"]["review_required"] is True
    assert patch["patch_strategy"]["solution_patterns"][0]["id"] == "executor_pattern_signature_fallback_review"
    assert patch["patch_strategy"]["llm_strategy"]["status"] == "not_requested"
    assert test_result["executor_strategy"]["deterministic_strategy"]["action"] == "verify_patch"


def test_programmer_executor_llm_strategy_is_hypothesis_only(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value.strip()\n", encoding="utf-8")
    spec, plan, test_plan = _executor_inputs()
    monkeypatch.setenv("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", "1")
    monkeypatch.setattr(
        "runtime.programmer_patch_strategy.call_json_chat",
        lambda messages, config=None: {
            "action": "propose_patch_recipe",
            "reason": "normalize input before returning",
            "expected_files": ["main.py"],
            "patch_recipe_hypothesis": {
                "recipe_type": "normalize_required_input",
                "target_symbol": "main.py:normalize",
                "diff": ["--- a/main.py", "+++ b/main.py", "@@ -1,2 +1,4 @@"],
            },
        },
    )

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    proposal = patch["patch_strategy"]["llm_strategy"]
    assert result["source_code_changes"] is False
    assert proposal["status"] == "proposed"
    assert proposal["authority"] == "hypothesis_only"
    assert patch["patch_strategy"]["sandbox_patch_candidate"]["status"] == "candidate_ready_for_sandbox_attempt"
    assert patch["patch_strategy"]["recommended_next_step"] == "run_reviewed_sandbox_patch_candidate"


def test_patch_strategy_blocks_import_runtime_boundary(tmp_path: Path):
    proposal = build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "main.py:run"}},
        test_plan={},
        synthesis={"status": "prepared", "reason": "required_input_guard_synthesized"},
        acceptance_summary={"signal_strength": "meta_only", "skipped_reason_counts": {"import_failed_runtime_error": 1}},
    )

    assert proposal["deterministic_strategy"]["action"] == "block_for_review"
    assert proposal["deterministic_strategy"]["reason"] == "import_time_runtime_boundary"
    assert proposal["executor_playbooks"][0]["id"] == "executor_playbook_import_runtime_boundary"
    assert proposal["executor_playbooks"][0]["authority"] == "advisory_playbook_only"


def test_patch_strategy_rebinds_nested_closure_target(tmp_path: Path):
    proposal = build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "main.py:filterfunc"}},
        test_plan={},
        synthesis={"status": "prepared", "reason": "required_input_guard_synthesized"},
        acceptance_summary={"signal_strength": "meta_only", "skipped_reason_counts": {"nested_function_requires_closure": 1}},
    )

    assert proposal["deterministic_strategy"]["action"] == "request_implementation_plan_contract_rebind"
    assert proposal["deterministic_strategy"]["reason"] == "nested_closure_target"


def test_patch_strategy_marks_skipped_synthesis_as_verified_no_patch(tmp_path: Path):
    proposal = build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "main.py:run"}},
        test_plan={},
        synthesis={"status": "skipped", "reason": "no_supported_patch_pattern", "patches": []},
        acceptance_summary={"signal_strength": "executable_callable"},
    )

    assert proposal["patch_quality"]["level"] == "verified_no_patch"
    assert proposal["patch_quality"]["review_required"] is False
    assert proposal["solution_patterns"][0]["id"] == "executor_pattern_verified_no_patch_callable"


def test_patch_strategy_requests_rebind_on_test_plan_target_drift(tmp_path: Path):
    proposal = build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "pkg/current.py:run"}},
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "target": "pkg/other.py:build",
                        "source_criterion": "Earlier slice `pkg/other.py:build` defines this behavior.",
                    }
                ]
            }
        },
        synthesis={"status": "prepared", "reason": "required_input_guard_synthesized"},
        acceptance_summary={"signal_strength": "executable_callable"},
    )

    assert proposal["contract_alignment"]["status"] == "target_drift"
    assert proposal["deterministic_strategy"]["action"] == "request_implementation_plan_contract_rebind"
    assert proposal["deterministic_strategy"]["reason"] == "test_plan_target_drift"
    assert proposal["contract_rebind_request"]["candidate_targets"][0]["target"] == "pkg/other.py:build"


def test_patch_strategy_blocks_invalid_llm_patch_candidate(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    spec, plan, test_plan = _executor_inputs()
    monkeypatch.setenv("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", "1")
    monkeypatch.setattr(
        "runtime.programmer_patch_strategy.call_json_chat",
        lambda messages, config=None: {
            "action": "propose_patch_recipe",
            "patch_recipe_hypothesis": {
                "recipe_type": "",
                "target_symbol": "other.py:normalize",
                "diff": ["--- /tmp/other.py", "+++ /tmp/other.py"],
            },
        },
    )

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    candidate = patch["patch_strategy"]["sandbox_patch_candidate"]
    assert result["source_code_changes"] is False
    assert candidate["status"] == "blocked_invalid_candidate"
    assert "target_symbol_mismatch" in candidate["errors"]
    assert "absolute_diff_path_forbidden" in candidate["errors"]


def test_programmer_executor_runs_valid_llm_candidate_in_sandbox(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def status():\n    return 'old'\n", encoding="utf-8")
    monkeypatch.setenv("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", "1")
    monkeypatch.setattr(
        "runtime.programmer_patch_strategy.call_json_chat",
        lambda messages, config=None: {
            "action": "propose_patch_recipe",
            "reason": "replace stale literal",
            "patch_recipe_hypothesis": {
                "recipe_type": "replace_literal",
                "target_symbol": "main.py:status",
                "diff": [
                    "--- a/main.py",
                    "+++ b/main.py",
                    "@@ -1,2 +1,2 @@",
                    " def status():",
                    "-    return 'old'",
                    "+    return 'new'",
                ],
            },
        },
    )

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan={
            "implementation_target": {"candidate": "main.py:status"},
            "patch_intent": {"target_symbol": "main.py:status"},
            "writable_scope": ["main.py:status"],
            "expected_files": ["main.py"],
            "verification_commands": ["python -m compileall ."],
        },
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "main.py:status",
                        "kind": "positive_contract_case",
                        "given": {},
                        "expect": {"result": "str"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "side_effect_boundary",
                        "target": "main.py:status",
                        "kind": "side_effect_scope_case",
                        "given": {"declared_scope": "writable_scope_only"},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ]
            }
        },
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    sandbox_main = Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py"
    assert result["status"] == "ok"
    assert patch["sandbox_candidate_attempt"]["status"] == "applied_in_sandbox"
    assert patch["patch_synthesis"]["reason"] == "llm_patch_candidate_applied_in_sandbox"
    assert "return 'new'" in sandbox_main.read_text(encoding="utf-8")
    assert "return 'old'" in (project / "main.py").read_text(encoding="utf-8")
    assert test_result["sandbox_candidate_attempt"]["status"] == "applied_in_sandbox"
    assert test_result["sandbox_candidate_repair_attempt"]["status"] == "not_attempted"


def test_programmer_executor_repairs_failed_llm_candidate_twice(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def status():\n    return 'old'\n", encoding="utf-8")
    calls = {"count": 0}

    def fake_llm(messages, config=None):
        calls["count"] += 1
        if calls["count"] == 1:
            replacement = "1"
            reason = "bad first candidate"
            removed = "-    return 'old'"
        elif calls["count"] == 2:
            replacement = "2"
            reason = "bad first repair"
            removed = "-    return 1"
        else:
            replacement = "'new'"
            reason = "repair return type"
            removed = "-    return 2"
        return {
            "action": "propose_patch_recipe",
            "reason": reason,
            "patch_recipe_hypothesis": {
                "recipe_type": "replace_literal",
                "target_symbol": "main.py:status",
                "diff": [
                    "--- a/main.py",
                    "+++ b/main.py",
                    "@@ -1,2 +1,2 @@",
                    " def status():",
                    removed,
                    f"+    return {replacement}",
                ],
            },
        }

    monkeypatch.setenv("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", "1")
    monkeypatch.setattr("runtime.programmer_patch_strategy.call_json_chat", fake_llm)
    monkeypatch.setattr("runtime.programmer_repair_strategy.call_json_chat", fake_llm)

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan={
            "implementation_target": {"candidate": "main.py:status"},
            "patch_intent": {"target_symbol": "main.py:status"},
            "writable_scope": ["main.py:status"],
            "expected_files": ["main.py"],
            "verification_commands": ["python -m compileall ."],
        },
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "main.py:status",
                        "kind": "positive_contract_case",
                        "given": {},
                        "expect": {"result": "str"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "side_effect_boundary",
                        "target": "main.py:status",
                        "kind": "side_effect_scope_case",
                        "given": {"declared_scope": "writable_scope_only"},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ]
            }
        },
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    sandbox_main = Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py"
    assert result["status"] == "ok"
    assert patch["sandbox_candidate_repair_attempt"]["status"] == "applied_in_sandbox"
    assert test_result["sandbox_candidate_repair_attempt"]["status"] == "applied_in_sandbox"
    assert len(test_result["sandbox_candidate_repair_attempts"]) == 2
    assert "return 'new'" in sandbox_main.read_text(encoding="utf-8")
    assert "return 'old'" in (project / "main.py").read_text(encoding="utf-8")
