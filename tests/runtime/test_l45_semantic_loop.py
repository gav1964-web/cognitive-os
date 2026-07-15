from __future__ import annotations

from pathlib import Path

from runtime.cognitive_control_plane import run_prompt_product_control_plane
from runtime.contract_registry import ContractRegistry
from runtime.l4_decision_table import decision_table_catalog, match_prompt_product_rule
from runtime.l45_model_modes import resolve_model_quality_mode
from runtime.l45_semantic_benchmark import run_l45_semantic_benchmark
from runtime.l4_semantic_validation import validate_l45_semantic_proposal
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.registry import CapabilityRegistry
from runtime.semantic_evidence_pack import build_semantic_evidence_pack
from runtime.semantic_reasoner import build_semantic_hypothesis_request, run_semantic_reasoner
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
    assert replay["outcome"]["next_action"] == "record_template_backlog"


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
    assert report["summary"]["case_count"] >= 4
    assert Path(report["report_path"]).is_file()
    assert any(row["actual"]["replay_path"] for row in report["cases"])


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
    contracts.validate_artifact(decision_table_catalog())
