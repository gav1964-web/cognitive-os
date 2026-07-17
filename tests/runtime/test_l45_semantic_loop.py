from __future__ import annotations

from pathlib import Path

from runtime.cognitive_control_plane import run_prompt_product_control_plane
from runtime.contract_registry import ContractRegistry
from runtime.l4_decision_table import decision_table_catalog, match_prompt_product_rule
from runtime.l45_model_modes import resolve_model_quality_mode
from runtime.l45_semantic_analytics import analyze_l45_semantic_benchmark, build_l45_risk_policy_gap_report
from runtime.l45_semantic_corpus import generate_l45_semantic_cases
from runtime.l45_semantic_benchmark import run_l45_semantic_benchmark
from runtime.l45_semantic_comparison import compare_l45_semantic_reports
from runtime.l45_semantic_eval_suite import run_l45_semantic_evaluation_suite
from runtime.l45_model_failure_analysis import analyze_l45_model_failures
from runtime.l4_semantic_validation import validate_l45_semantic_proposal
from runtime.prompt_boundary_classifier import classify_prompt_boundary
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.registry import CapabilityRegistry
from runtime.semantic_evidence_pack import build_semantic_evidence_pack
from runtime.semantic_reasoner import (
    build_developer_improvement_request,
    build_semantic_hypothesis_request,
    build_successful_resolution_candidate,
    run_semantic_reasoner,
)
from runtime.semantic_replay import build_semantic_replay_record


def test_semantic_evidence_pack_is_bounded_l4_fact_packet():
    gate = evaluate_prompt_adequacy(
        "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, нормализует name, сохраняет CSV, имеет README и тесты."
    ).to_dict()
    decision = run_prompt_product_control_plane(prompt=gate["prompt"], prompt_adequacy=gate, supported_template=None)

    pack = build_semantic_evidence_pack(
        control_plane_decision=decision,
        prompt=gate["prompt"],
        prompt_adequacy=gate,
        known_templates=["csv_sort_cli"],
    )

    assert pack["artifact_type"] == "SemanticEvidencePack"
    assert pack["authority"]["may_execute"] is False
    assert pack["control_facts"]["semantic_escalation"]["l4_5_required"] is True
    assert "build_package" in pack["forbidden_actions"]


def test_semantic_replay_records_full_request_proposal_validation_path():
    gate = evaluate_prompt_adequacy(
        "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, нормализует name, сохраняет CSV, имеет README и тесты."
    ).to_dict()
    decision = run_prompt_product_control_plane(prompt=gate["prompt"], prompt_adequacy=gate, supported_template=None)
    request = build_semantic_hypothesis_request(control_plane_decision=decision, context={"prompt": gate["prompt"]})
    assert request is not None
    proposal = run_semantic_reasoner(request=request)
    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)

    replay = build_semantic_replay_record(
        request=request,
        proposal=proposal,
        validation=validation,
        model_quality_mode="deterministic",
    )

    assert replay["artifact_type"] == "SemanticProposalReplay"
    assert replay["audit"]["l4_status"] == "accepted"
    assert replay["outcome"]["next_action"] == "record_developer_improvement_request"


def test_l45_records_successful_resolution_candidate_for_existing_means():
    gate = evaluate_prompt_adequacy(
        "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, сортирует строки по колонке name, сохраняет CSV-файл, имеет README и тесты."
    ).to_dict()
    decision = run_prompt_product_control_plane(prompt=gate["prompt"], prompt_adequacy=gate, supported_template=None)
    pack = build_semantic_evidence_pack(
        control_plane_decision=decision,
        prompt=gate["prompt"],
        prompt_adequacy=gate,
        known_templates=["csv_sort_cli"],
    )
    request = build_semantic_hypothesis_request(
        control_plane_decision=decision,
        context={"prompt": gate["prompt"], "evidence_pack": pack},
    )
    assert request is not None

    proposal = run_semantic_reasoner(request=request)
    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)
    candidate = build_successful_resolution_candidate(proposal)

    assert proposal["hypothesis_type"] == "successful_existing_resolution"
    assert validation["accepted_action"] == "record_successful_resolution_candidate"
    assert candidate is not None
    assert candidate["requires_repeated_successes"] is True


def test_l45_records_developer_request_when_existing_means_fail():
    gate = evaluate_prompt_adequacy(
        "Напиши CLI-утилиту с зависимостью openpyxl, которая читает XLSX-файл, сохраняет JSON-отчёт, имеет README и тесты."
    ).to_dict()
    decision = run_prompt_product_control_plane(prompt=gate["prompt"], prompt_adequacy=gate, supported_template=None)
    request = build_semantic_hypothesis_request(control_plane_decision=decision, context={"prompt": gate["prompt"]})
    assert request is not None

    proposal = run_semantic_reasoner(request=request)
    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)
    improvement = build_developer_improvement_request(proposal)

    assert proposal["hypothesis_type"] == "developer_improvement_request"
    assert validation["accepted_action"] == "record_developer_improvement_request"
    assert improvement is not None
    assert improvement["requires_developer"] is True


def test_l4_decision_table_exposes_crystallization_rules():
    catalog = decision_table_catalog()
    rule = match_prompt_product_rule(prompt_adequacy_status="ready", supported_template=None)

    assert catalog["artifact_type"] == "L4DecisionTable"
    assert catalog["rule_count"] >= 4
    assert rule is not None
    assert rule["next_action"] == "request_l45_semantic_hypothesis"


def test_l45_model_quality_modes_are_explicit_and_non_authoritative():
    policy = resolve_model_quality_mode("model_with_human_review")

    assert policy["use_model"] is True
    assert policy["requires_human_review"] is True
    assert policy["trusted_for_action"] is False


def test_l45_semantic_benchmark_passes_deterministic_cases(tmp_path: Path):
    report = run_l45_semantic_benchmark(root=tmp_path, write=True)

    assert report["artifact_type"] == "L45SemanticBenchmarkReport"
    assert report["status"] == "ok"
    assert report["summary"]["case_count"] >= 20
    assert Path(report["report_path"]).is_file()
    assert any(row["actual"]["replay_path"] for row in report["cases"])


def test_l45_generated_corpus_is_seeded_and_runs_200_cases(tmp_path: Path):
    corpus = generate_l45_semantic_cases(size=200, seed=45)
    again = generate_l45_semantic_cases(size=200, seed=45)
    report = run_l45_semantic_benchmark(root=tmp_path, write=False, generated_corpus_size=200, seed=45)

    assert len(corpus) == 200
    assert corpus == again
    assert len({row["case_id"] for row in corpus}) == 200
    assert report["status"] == "ok"
    assert report["corpus"]["kind"] == "generated"
    assert report["summary"]["case_count"] == 200


def test_l45_generated_corpus_profiles_are_seeded_and_distinct(tmp_path: Path):
    risk = generate_l45_semantic_cases(size=50, seed=45, profile="risk_heavy")
    known = generate_l45_semantic_cases(size=50, seed=45, profile="known_template_regression")
    report = run_l45_semantic_benchmark(
        root=tmp_path,
        write=False,
        generated_corpus_size=50,
        seed=45,
        corpus_profile="risk_heavy",
    )

    assert risk == generate_l45_semantic_cases(size=50, seed=45, profile="risk_heavy")
    assert risk != known
    assert report["status"] == "ok"
    assert report["corpus"]["profile"] == "risk_heavy"
    assert any(
        row["actual"]["l4_action"] == "record_developer_improvement_request"
        for row in report["cases"]
    )


def test_prompt_boundary_classifier_marks_unsupported_surfaces():
    result = classify_prompt_boundary(
        "Создай мобильное приложение с push-уведомлениями и публикацией в store.",
        system_type=None,
        missing=["system_type_defined"],
    ).to_dict()

    assert result["artifact_type"] == "PromptBoundaryClassification"
    assert result["boundary"] == "unsupported_product_surface"
    assert "mobile_app" in result["unsupported_markers"]


def test_l4_gate_routes_risky_unknown_templates_to_developer_requests(tmp_path: Path):
    report = run_l45_semantic_benchmark(root=tmp_path, write=False)
    by_id = {row["case_id"]: row for row in report["cases"]}

    source_edit = by_id["source_edit_boundary"]
    desktop_gui = by_id["desktop_gui_boundary"]

    assert source_edit["actual"]["l4_action"] == "record_developer_improvement_request"
    assert source_edit["actual"]["backlog_created"] is False
    assert source_edit["actual"]["developer_request_created"] is True
    assert desktop_gui["actual"]["l4_action"] == "ask_clarification"
    assert desktop_gui["actual"]["policy_review"]["applied_rule"] == "unsupported_surface_requires_clarification"


def test_l45_analytics_and_policy_gap_reports_are_contract_artifacts(tmp_path: Path):
    report = run_l45_semantic_benchmark(
        root=tmp_path,
        write=False,
        generated_corpus_size=80,
        seed=45,
        corpus_profile="risk_heavy",
    )
    analytics = analyze_l45_semantic_benchmark(report)
    gaps = build_l45_risk_policy_gap_report(report)

    assert analytics["artifact_type"] == "L45SemanticCorpusAnalyticsReport"
    assert analytics["summary"]["case_count"] == 80
    assert analytics["policy_signals"]["risk_boundary_to_normal_backlog"] == 0
    assert analytics["category_counts"]["unknown_template"] > 0
    assert gaps["artifact_type"] == "L45RiskPolicyGapReport"
    assert gaps["status"] == "ok"
    assert gaps["summary"]["gap_count"] == 0


def test_l45_semantic_comparison_reports_no_clear_difference_for_same_reports(tmp_path: Path):
    deterministic = run_l45_semantic_benchmark(root=tmp_path, write=False)
    model = run_l45_semantic_benchmark(root=tmp_path, write=False, use_model=False, model_quality_mode="deterministic")

    comparison = compare_l45_semantic_reports(deterministic_report=deterministic, model_report=model)

    assert comparison["artifact_type"] == "L45SemanticComparisonReport"
    assert comparison["status"] == "ok"
    assert comparison["summary"]["case_count"] == deterministic["summary"]["case_count"]
    assert comparison["summary"]["deterministic_better"] == 0


def test_l45_semantic_evaluation_suite_runs_profiles_without_model(tmp_path: Path):
    report = run_l45_semantic_evaluation_suite(
        root=tmp_path,
        generated_corpus_size=20,
        seed=45,
        profiles=["risk_heavy", "unknown_template_heavy"],
        include_model=False,
        write=True,
    )

    assert report["artifact_type"] == "L45SemanticEvaluationSuiteReport"
    assert report["status"] == "ok"
    assert report["summary"]["profile_count"] == 2
    assert report["summary"]["risk_policy_gap_count"] == 0
    assert Path(report["report_path"]).is_file()
    assert all(row["deterministic"]["status"] == "ok" for row in report["profiles"])


def test_l45_model_failure_analysis_counts_blocked_model_cases():
    comparison = {
        "cases": [
            {
                "case_id": "case_1",
                "verdict": "deterministic_better",
                "deterministic": {"status": "ok", "l4_action": "record_template_backlog"},
                "model": {
                    "status": "failed",
                    "l4_action": "blocked",
                    "validation_failed_codes": ["risks_present"],
                    "raw_model_output_used": True,
                },
            }
        ]
    }

    report = analyze_l45_model_failures(comparison_reports=[comparison])

    assert report["artifact_type"] == "L45ModelFailureAnalysisReport"
    assert report["summary"]["model_failure_count"] == 1
    assert report["summary"]["failed_code_counts"]["risks_present"] == 1


def test_l45_hardening_synthesizes_missing_model_risks():
    request = {
        "artifact_type": "SemanticHypothesisRequest",
        "layer": "L4.5",
        "source_decision": {"mode": "prompt_to_product"},
        "trigger_reasons": ["no_supported_package_template"],
        "allowed_hypothesis_types": ["new_template_candidate"],
        "output_contract": {
            "required_fields": [
                "hypothesis_type",
                "proposal",
                "confidence",
                "evidence_refs",
                "risks",
                "return_to_gate",
            ],
        },
        "forbidden_actions": ["build_package"],
        "return_path": {"target_layer": "L4.0"},
    }
    proposal = run_semantic_reasoner(
        request=request,
        proposal_provider=lambda _request: {
            "hypothesis_type": "new_template_candidate",
            "proposal": {"template_id": "candidate", "actions": ["record_backlog_item"]},
            "confidence": 0.7,
            "evidence_refs": ["test"],
            "risks": [],
            "return_to_gate": True,
        },
    )

    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)

    assert proposal["hardening"]["risks_synthesized"] is True
    assert proposal["risks"]
    assert validation["status"] == "accepted"


def test_contract_registry_knows_l45_loop_artifacts():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    contracts = ContractRegistry.from_capability_registry(registry)

    contracts.validate_artifact(
        {
            "artifact_type": "SemanticEvidencePack",
            "layer": "L4.0",
            "status": "ready",
            "prompt_facts": {},
            "control_facts": {},
            "forbidden_actions": [],
            "authority": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "SemanticProposalReplay",
            "status": "recorded",
            "request": {},
            "proposal": {},
            "validation": {},
            "model_quality_mode": "deterministic",
            "outcome": {},
            "audit": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticBenchmarkReport",
            "status": "ok",
            "model_quality_mode": "deterministic",
            "summary": {},
            "cases": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticCorpusAnalyticsReport",
            "status": "ok",
            "source_report": {},
            "summary": {},
            "boundary_counts": {},
            "action_counts": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45RiskPolicyGapReport",
            "status": "ok",
            "source_report": {},
            "summary": {},
            "gaps": [],
            "policy_recommendations": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticComparisonReport",
            "status": "ok",
            "summary": {},
            "cases": [],
            "interpretation": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticEvaluationSuiteReport",
            "status": "ok",
            "config": {},
            "summary": {},
            "profiles": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45ModelFailureAnalysisReport",
            "status": "ok",
            "summary": {},
            "failures": [],
            "recommendations": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "PromptBoundaryClassification",
            "status": "ok",
            "boundary": "bounded_supported_class",
            "confidence": 0.9,
            "reasons": [],
            "recommended_action": "route_to_l4_gate",
        }
    )
    contracts.validate_artifact(decision_table_catalog())
