from __future__ import annotations

import json
from pathlib import Path

from runtime.project_benchmark import analyze_project
from runtime.local_inference import LocalInferenceConfig
from runtime.role_skills import (
    run_architect_skill,
    run_implementer_skill,
    run_reviewer_skill,
    run_spec_writer_skill,
    run_tester_skill,
)


ROOT = Path(__file__).resolve().parents[2]


def test_architect_skill_returns_typed_adr():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]

    artifact = run_architect_skill(goal="Extract first safe capability", project_report=report)

    assert artifact["artifact_type"] == "ArchitectureDecisionRecord"
    assert artifact["role"] == "architect"
    assert artifact["status"] == "ok"
    assert artifact["subsystem_boundaries"]
    assert artifact["capability_model"]
    assert len(artifact["architecture_options"]) >= 2
    assert artifact["chosen_option"]["id"]
    assert artifact["rejected_options"]
    assert artifact["source_context"]["main.py:normalize_text"]["snippet"]["text"]
    assert artifact["source_context"]["main.py:normalize_text"]["callers"] == ["main.py:main"]
    assert artifact["source_context"]["main.py:write_json"]["central_flow_node"]["side_effects"] == ["filesystem"]
    assert artifact["spec_writer_brief"]["acceptance_targets"]
    assert artifact["next_artifact"]["recommended_role"] == "spec_writer"
    assert artifact["architect_advisory"]["source"] == "deterministic"
    assert artifact["forbidden_actions_observed"] == []


def test_architect_skill_llm_advisory_falls_back():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    config = LocalInferenceConfig(base_url="http://127.0.0.1:9/v1", model="missing", timeout_seconds=0.05)

    artifact = run_architect_skill(goal="Extract first safe capability", project_report=report, advisory_config=config)

    assert artifact["status"] == "ok"
    assert artifact["architect_advisory"]["source"] == "deterministic_fallback"
    assert artifact["architect_advisory"]["llm_invoked"] is False


def test_architect_skill_accepts_mocked_llm_advisory(monkeypatch):
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]

    def fake_call_json_chat(messages, *, config=None):
        return {
            "chosen_option_id": "contract_hardening_first",
            "reason": "Mocked advisory prefers contract_hardening_first because the capability model needs stronger contracts.",
            "additional_risks": [
                {
                    "description": "Capability model contracts may be too weak for promotion.",
                    "evidence": "main.py:normalize_text",
                }
            ],
            "summary": "Mocked advisory applied.",
        }

    monkeypatch.setattr("runtime.role_architect_llm.call_json_chat", fake_call_json_chat)
    config = LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="mock", provider_label="test_llm")

    artifact = run_architect_skill(goal="Extract first safe capability", project_report=report, advisory_config=config)

    assert artifact["architect_advisory"]["source"] == "test_llm"
    assert artifact["architect_advisory"]["llm_invoked"] is True
    assert artifact["architect_advisory"]["accepted"] is True
    assert artifact["architect_advisory"]["advisory_delta_score"] > 0
    assert "contract_risk" in artifact["architect_advisory"]["quality_tags"]
    assert artifact["architect_advisory"]["accepted_risks"][0]["quality_tags"]
    assert artifact["chosen_option"]["id"] == "contract_hardening_first"
    assert any(risk["source"] == "architect_llm_advisory" for risk in artifact["risks"])


def test_architect_skill_sends_evidence_sources_to_llm(monkeypatch):
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    captured = {}

    def fake_call_json_chat(messages, *, config=None):
        captured["payload"] = json.loads(messages[-1]["content"])
        return {
            "chosen_option_id": "minimal_safe_extraction",
            "reason": "Current choice remains best.",
            "additional_risks": [],
            "summary": "No source-backed advisory changes.",
        }

    monkeypatch.setattr("runtime.role_architect_llm.call_json_chat", fake_call_json_chat)
    config = LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="mock", provider_label="test_llm")

    artifact = run_architect_skill(goal="Extract first safe capability", project_report=report, advisory_config=config)

    assert artifact["architect_advisory"]["accepted"] is False
    assert "main.py:normalize_text" in captured["payload"]["evidence_sources"]
    assert captured["payload"]["source_context"]["main.py:normalize_text"]["snippet"]["text"]
    assert captured["payload"]["source_context"]["main.py:normalize_text"]["callers"] == ["main.py:main"]
    assert captured["payload"]["current_choice"] == "minimal_safe_extraction"


def test_architect_skill_rejects_generic_llm_advisory(monkeypatch):
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]

    def fake_call_json_chat(messages, *, config=None):
        return {
            "chosen_option_id": "minimal_safe_extraction",
            "reason": "This option seems reasonable.",
            "additional_risks": ["None identified beyond the tradeoffs mentioned."],
            "summary": "No meaningful changes.",
        }

    monkeypatch.setattr("runtime.role_architect_llm.call_json_chat", fake_call_json_chat)
    config = LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="mock", provider_label="test_llm")

    artifact = run_architect_skill(goal="Extract first safe capability", project_report=report, advisory_config=config)

    assert artifact["architect_advisory"]["llm_invoked"] is True
    assert artifact["architect_advisory"]["accepted"] is False
    assert artifact["architect_advisory"]["advisory_delta_score"] == 0
    assert not any(risk["source"] == "architect_llm_advisory" for risk in artifact["risks"])


def test_architect_skill_rejects_duplicate_llm_risk(monkeypatch):
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "scraper_with_retry_and_cache"
    report = analyze_project(project_dir)["project_map_report"]

    def fake_call_json_chat(messages, *, config=None):
        return {
            "chosen_option_id": "minimal_safe_extraction",
            "reason": "Current choice remains best.",
            "additional_risks": [
                {
                    "description": "Potential problems related to unpinned dependencies.",
                    "evidence_source": "ProjectMapReport.risks",
                }
            ],
            "summary": "Repeats known dependency risk.",
        }

    monkeypatch.setattr("runtime.role_architect_llm.call_json_chat", fake_call_json_chat)
    config = LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="mock", provider_label="test_llm")

    artifact = run_architect_skill(goal="Assess scraper", project_report=report, advisory_config=config)

    assert artifact["architect_advisory"]["accepted"] is False
    assert artifact["architect_advisory"]["rejected_items"][0]["reason"] == "duplicates existing risk"


def test_spec_writer_skill_returns_technical_spec():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)

    spec = run_spec_writer_skill(architecture_decision=adr)

    assert spec["artifact_type"] == "TechnicalSpec"
    assert spec["role"] == "spec_writer"
    assert spec["status"] == "ok"
    assert spec["requirements"]
    assert spec["source_evidence"]
    assert spec["extraction_contract"]["candidate"]
    assert spec["extraction_contract"]["ranked_candidates"][0]["source"] == spec["extraction_contract"]["candidate"]
    assert spec["extraction_contract"]["selection_reason"]
    assert spec["extraction_contract"]["candidate_score"] > 0
    assert spec["acceptance_criteria"]
    assert any("main.py:" in row["criterion"] for row in spec["acceptance_criteria"])
    assert spec["traceability_table"]
    assert spec["implementation_handoff"]["recommended_role"] == "implementer"
    assert spec["forbidden_actions_observed"] == []


def test_spec_writer_prefers_core_transform_over_runtime_boundary():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate extraction candidate ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/_api.py:request",
                "pkg/_reloader.py:trigger_reload",
                "pkg/core.py:normalize_headers",
            ],
        },
        "traceability": [
            {"source": "pkg/_api.py:request", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/core.py:normalize_headers", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "pkg/_api.py:request": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "url", "annotation": "str"}], "returns": "Response"},
                "snippet": {"text": "def request(url): ..."},
            },
            "pkg/_reloader.py:trigger_reload": {
                "kind": "pure_transform",
                "signature": {"args": [], "returns": "None"},
                "snippet": {"text": "def trigger_reload(): ..."},
            },
            "pkg/core.py:normalize_headers": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "headers", "annotation": "dict"}], "returns": "dict"},
                "snippet": {"text": "def normalize_headers(headers): ..."},
            },
        },
    }

    spec = run_spec_writer_skill(architecture_decision=adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/core.py:normalize_headers"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    reasons = " ".join(ranked["pkg/_api.py:request"]["reasons"])
    assert "API/runtime boundary" in reasons


def test_implementer_skill_returns_implementation_plan():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)
    spec = run_spec_writer_skill(architecture_decision=adr)

    plan = run_implementer_skill(technical_spec=spec)

    assert plan["artifact_type"] == "ImplementationPlan"
    assert plan["role"] == "implementer"
    assert plan["status"] == "ok"
    assert plan["implementation_target"]["candidate"] == spec["extraction_contract"]["candidate"]
    assert plan["contract_binding"]["binding_status"] == "bound_to_extraction_contract"
    assert plan["contract_binding"]["input_contract"] == spec["extraction_contract"]["input_contract"]
    assert plan["contract_binding"]["output_contract"] == spec["extraction_contract"]["output_contract"]
    assert spec["extraction_contract"]["candidate"] in plan["implementation_steps"][0]["action"]
    assert plan["patch_scope"]
    assert plan["expected_files"]
    assert plan["implementation_units"]
    assert plan["change_plan"]
    assert plan["implementation_blueprint"]["artifact_type"] == "ImplementationBlueprint"
    assert plan["implementation_blueprint"]["status"] == "ready"
    assert plan["implementation_blueprint"]["target"] == spec["extraction_contract"]["candidate"]
    assert plan["patch_intent"]["artifact_type"] == "PatchIntent"
    assert plan["patch_intent"]["mode"] == "sandbox_first"
    assert plan["patch_intent"]["target_symbol"] == spec["extraction_contract"]["candidate"]
    assert plan["patch_intent"]["apply_source_default"] is False
    assert plan["executor_handoff"]["artifact_type"] == "ExecutorHandoff"
    assert plan["executor_handoff"]["recommended_tool"] == "tools/apply_implementation_plan.py"
    assert plan["executor_handoff"]["apply_source_default"] is False
    assert plan["patch_package_contract"]["artifact_type"] == "PatchPackage"
    assert plan["patch_package_contract"]["apply_policy"].startswith("build isolated patch package")
    assert plan["dependency_policy"]["new_runtime_dependencies"] == "forbidden_by_default"
    assert plan["quality_gates"]
    assert plan["debug_rework_policy"]["output_artifact"] == "BoundedReworkPlan"
    assert plan["verification_commands"]
    assert plan["rollback_plan"]["registry_policy"]
    assert plan["acceptance_mapping"]
    assert plan["next_artifact"]["recommended_role"] == "tester"
    assert plan["forbidden_actions_observed"] == []


def test_tester_skill_returns_test_plan():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)
    spec = run_spec_writer_skill(architecture_decision=adr)
    implementation = run_implementer_skill(technical_spec=spec)

    test_plan = run_tester_skill(technical_spec=spec, implementation_plan=implementation)

    assert test_plan["artifact_type"] == "TestPlan"
    assert test_plan["role"] == "tester"
    assert test_plan["status"] == "ok"
    assert test_plan["test_target"]["candidate"] == implementation["implementation_target"]["candidate"]
    assert test_plan["test_strategy"]["writable_scope"] == implementation["writable_scope"]
    assert test_plan["test_strategy"]["evidence_scope"] == implementation["evidence_scope"]
    assert test_plan["contract_test_matrix"]
    assert any(row["target"] == implementation["implementation_target"]["candidate"] for row in test_plan["contract_test_matrix"])
    assert any(row["target"] == implementation["implementation_target"]["candidate"] for row in test_plan["negative_tests"])
    assert test_plan["acceptance_tests"]
    assert test_plan["executable_acceptance"]["status"] == "ready"
    assert test_plan["executable_acceptance"]["obligations"]
    assert test_plan["negative_tests"]
    assert test_plan["smoke_checklist"]
    assert test_plan["regression_risks"]
    assert test_plan["reproducibility"]["required_artifacts"]
    assert test_plan["next_artifact"]["recommended_role"] == "reviewer"
    assert test_plan["forbidden_actions_observed"] == []


def test_tester_skill_covers_all_acceptance_criteria_but_bounds_executable_obligations():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)
    spec = run_spec_writer_skill(architecture_decision=adr)
    for index in range(20):
        spec["acceptance_criteria"].append(
            {
                "id": f"AC-EXTRA-{index + 1:03d}",
                "criterion": f"Extra source-backed acceptance criterion {index + 1}",
                "verification": "explicit review checklist",
                "source": f"extra.py:source_{index + 1}",
            }
        )
    implementation = run_implementer_skill(technical_spec=spec)

    test_plan = run_tester_skill(technical_spec=spec, implementation_plan=implementation)

    spec_ids = {row["id"] for row in spec["acceptance_criteria"]}
    tested_ids = {row["acceptance_id"] for row in test_plan["acceptance_tests"]}
    executable_positive = [
        row for row in test_plan["executable_acceptance"]["obligations"] if row.get("kind") == "positive_contract_case"
    ]
    assert spec_ids <= tested_ids
    assert len(executable_positive) == 10
    assert any(row["execution_mode"] == "review_checklist" for row in test_plan["acceptance_tests"])


def test_reviewer_skill_returns_review_findings():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)
    spec = run_spec_writer_skill(architecture_decision=adr)
    implementation = run_implementer_skill(technical_spec=spec)
    test_plan = run_tester_skill(technical_spec=spec, implementation_plan=implementation)

    review = run_reviewer_skill(
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "ok", "executable_acceptance_result": {"status": "passed"}},
    )

    assert review["artifact_type"] == "ReviewFindings"
    assert review["role"] == "reviewer"
    assert review["status"] == "ok"
    assert review["findings"]
    assert review["review_target"]["candidate"] == implementation["implementation_target"]["candidate"]
    assert review["coverage_assessment"]["target_covered"] is True
    assert review["coverage_assessment"]["contract_matrix_rows"] > 0
    assert review["conformance_status"] == "passed"
    assert all(row["passed"] for row in review["conformance_checks"])
    assert review["risk_assessment"]
    assert review["contract_violations"] == []
    assert review["recommendation"] in {"approve", "approve_with_risks", "request_rework"}
    assert review["forbidden_actions_observed"] == []


def test_reviewer_rejects_writable_scope_expansion():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)
    spec = run_spec_writer_skill(architecture_decision=adr)
    implementation = run_implementer_skill(technical_spec=spec)
    test_plan = run_tester_skill(technical_spec=spec, implementation_plan=implementation)
    test_plan["test_strategy"]["writable_scope"] = implementation["patch_scope"]

    review = run_reviewer_skill(
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "ok"},
    )

    assert review["recommendation"] == "request_rework"
    assert review["conformance_status"] == "failed"
    assert any(row["code"] == "test_writable_scope_mismatch" for row in review["contract_violations"])


def test_reviewer_rejects_failed_executable_acceptance_result():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=report)
    spec = run_spec_writer_skill(architecture_decision=adr)
    implementation = run_implementer_skill(technical_spec=spec)
    test_plan = run_tester_skill(technical_spec=spec, implementation_plan=implementation)

    review = run_reviewer_skill(
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "failed", "executable_acceptance_result": {"status": "failed"}},
    )

    assert review["recommendation"] == "request_rework"
    assert review["conformance_status"] == "failed"
    assert any(row["code"] == "executable_acceptance_passed_or_absent" and not row["passed"] for row in review["conformance_checks"])


def test_architect_skill_runs_on_benchmark_corpus():
    projects = sorted((ROOT / "benchmarks" / "project_analyzer" / "projects").iterdir())

    for project_dir in projects:
        if not project_dir.is_dir():
            continue
        report = analyze_project(project_dir)["project_map_report"]
        artifact = run_architect_skill(goal=f"Assess {project_dir.name}", project_report=report)
        assert artifact["status"] == "ok", project_dir.name
        assert artifact["chosen_option"]["id"], project_dir.name
        assert artifact["spec_writer_brief"]["scope"], project_dir.name
