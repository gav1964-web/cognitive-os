import json

from runtime.hypothesis_compiler_contract import build_candidate, validate_candidate
from runtime.self_improvement_capability_request import capability_development_requests
from runtime.self_improvement_hypothesis_compiler import (
    _synthesis_request,
    compile_existing_evidence,
    compile_hypothesis,
    enrich_diagnosis,
)


def _report(project: str, *, reason="positive_sample_execution_failed", selected="app.py:weak", trained="app.py:weak", delta=0.0):
    return {
        "project": project,
        "status": "hypothesis_not_confirmed",
        "baseline": {
            "status": "ok",
            "project_min_score": 7.5,
            "selected_extraction_candidate": selected,
            "selected_candidate_quality": {
                "structural_evidence": {
                    "observed_side_effects": [],
                    "output_inference_basis": "return_expression",
                },
            },
            "downstream_evidence": {
                "reason": reason,
                "summary": {"skipped_targets": [{
                    "reason": "positive_sample_execution_failed",
                    "detail": "object has no attribute 'value'",
                }]},
            },
        },
        "trained_attempt": {
            "project_min_score": 7.5 + delta,
            "selected_extraction_candidate": trained,
        },
        "diagnosis": {
            "failure_class": "executable_sample_contract",
            "target_roles": ["spec_writer"],
        },
        "outcome": {
            "status": "candidate_improvement_confirmed" if delta > 0 else "hypothesis_not_confirmed",
            "score_delta": delta,
        },
        "improvement_plugin_cycle": {"attempts": []},
    }


def _write_history(root, reports):
    directory = root / "artifacts" / "self_improvement"
    directory.mkdir(parents=True)
    for index, report in enumerate(reports):
        (directory / f"self_improvement_20260101T00000{index}Z.json").write_text(
            json.dumps(report), encoding="utf-8",
        )


def test_compiler_waits_for_independent_cluster_evidence(tmp_path):
    result = compile_hypothesis(root=tmp_path, report=_report("one"), write=False, use_model=False)

    assert result["status"] == "collecting_evidence"
    assert result["cluster"]["observed_project_count"] == 1
    assert result["candidates"] == []


def test_compiler_builds_fixture_hypothesis_and_keeps_counterexample(tmp_path):
    positives = [_report(name) for name in ("one", "two", "three")]
    counterexample = _report("control", reason="import_failed_missing_module")
    _write_history(tmp_path, [*positives[1:], counterexample])

    result = compile_hypothesis(
        root=tmp_path, report=positives[0], write=False,
        synthesizer=lambda _request: {"abstraction": {
            "problem_pattern": "receiver fixtures omit a source-proven attribute",
            "applicability": "value-like receiver contracts",
            "counterexample_risk": "dependency failures need a different adapter route",
        }},
    )

    candidate = result["candidates"][0]
    assert result["status"] == "compiled"
    assert candidate["candidate_type"] == "fixture_strategy"
    assert candidate["evidence_refs"] == ["one", "three", "two"]
    assert candidate["counterexample_refs"] == ["control"]
    assert candidate["required_plugin_contract"]["capability"] == "bounded_parameter_strategy_extension"
    assert candidate["abstraction"]["problem_pattern"].startswith("receiver fixtures")
    assert candidate["authority"] == "hypothesis_only"


def test_compiler_normalizes_flat_model_abstraction(tmp_path):
    positives = [_report(name) for name in ("one", "two", "three")]
    _write_history(tmp_path, positives[1:])

    result = compile_hypothesis(
        root=tmp_path, report=positives[0], write=False,
        synthesizer=lambda _request: {
            "problem_pattern": "flat but valid abstraction",
            "applicability": "bounded receiver fixtures",
            "counterexample_risk": "dependency boundaries",
        },
    )

    assert result["model_trace"]["status"] == "ok"
    assert result["candidates"][0]["abstraction"]["problem_pattern"] == (
        "flat but valid abstraction"
    )


def test_compiler_normalizes_dotted_model_abstraction(tmp_path):
    positives = [_report(name) for name in ("one", "two", "three")]
    _write_history(tmp_path, positives[1:])

    result = compile_hypothesis(
        root=tmp_path, report=positives[0], write=False,
        synthesizer=lambda _request: {
            "abstraction.problem_pattern": "dotted abstraction",
            "abstraction.applicability": "bounded receiver fixtures",
            "abstraction.counterexample_risk": "dependency boundaries",
        },
    )

    assert result["model_trace"]["status"] == "ok"
    assert result["candidates"][0]["abstraction"]["problem_pattern"] == "dotted abstraction"


def test_compiler_reuses_model_abstraction_at_same_evidence_milestone(tmp_path):
    positives = [_report(name) for name in ("one", "two", "three")]
    _write_history(tmp_path, positives[1:])
    calls = []

    def synthesize(_request):
        calls.append(True)
        return {"abstraction": {
            "problem_pattern": "cached abstraction",
            "applicability": "bounded receiver fixtures",
            "counterexample_risk": "dependency boundaries",
        }}

    compile_hypothesis(
        root=tmp_path, report=positives[0], write=True, synthesizer=synthesize,
    )
    repeated = compile_hypothesis(
        root=tmp_path, report=positives[0], write=True, synthesizer=synthesize,
    )

    assert calls == [True]
    assert repeated["model_trace"]["status"] == "cached"


def test_compiler_prefers_selection_rule_for_repeated_measured_reselection(tmp_path):
    reports = [
        _report(name, trained=f"app.py:better_{name}", delta=2.1)
        for name in ("one", "two", "three")
    ]
    _write_history(tmp_path, reports[1:])

    result = compile_hypothesis(
        root=tmp_path, report=reports[0], write=False, use_model=False,
    )

    candidate = result["candidates"][0]
    assert candidate["candidate_type"] == "candidate_selection_rule"
    assert candidate["required_plugin_contract"]["capability"] == (
        "candidate_selection_structural_discriminator_synthesis"
    )


def test_compiler_plans_evidence_before_requesting_new_plugin(tmp_path):
    reports = [_report(name, selected=None, trained=None) for name in ("one", "two", "three")]
    for report in reports:
        report["diagnosis"]["failure_class"] = "role_quality"
        report["baseline"]["downstream_evidence"] = {}
    _write_history(tmp_path, reports[1:])

    result = compile_hypothesis(
        root=tmp_path, report=reports[0], write=False, use_model=False,
    )

    candidate = result["candidates"][0]
    assert candidate["candidate_type"] == "evidence_collection_plan"
    assert candidate["required_plugin_contract"]["capability"] == (
        "bounded_hypothesis_evidence_collection"
    )


def test_candidate_contract_rejects_executable_model_output():
    candidate = build_candidate(
        candidate_type="fixture_strategy",
        failure_class="executable_sample_contract",
        portable_signature="failure|pure|return_expression",
        semantic_context=[], evidence_refs=["one", "two", "three"], counterexample_refs=[],
        invariant="Repeated receiver mismatch", desired_effect="Build a bounded fixture",
        capability="bounded_parameter_strategy_extension", gates=["independent_holdout"],
    )
    candidate["abstraction"]["code"] = "import os"

    accepted, errors = validate_candidate(
        candidate,
        allowed_types={"fixture_strategy"},
        allowed_capabilities={"bounded_parameter_strategy_extension"},
        forbidden_fields={"code", "diff", "patch"},
        evidence_refs={"one", "two", "three"}, counterexample_refs=set(),
    )

    assert accepted == {}
    assert "forbidden_fields:code" in errors


def test_compiled_hypothesis_routes_to_plugin_foundry_request(tmp_path):
    reports = [_report(name) for name in ("one", "two", "three")]
    _write_history(tmp_path, reports[1:])
    compilation = compile_hypothesis(
        root=tmp_path, report=reports[0], write=False, use_model=False,
    )
    training = [{"hypothesis_compilation": compilation}]

    requests = capability_development_requests(tmp_path, training, minimum_projects=3)

    assert len(requests) == 1
    assert requests[0]["hypothesis_id"] == compilation["candidates"][0]["hypothesis_id"]
    assert requests[0]["missing_capability"] == "bounded_parameter_strategy_extension"
    assert requests[0]["counterexample_projects"] == []


def test_compiler_enriches_diagnosis_without_granting_authority(tmp_path):
    reports = [_report(name) for name in ("one", "two", "three")]
    _write_history(tmp_path, reports[1:])
    compilation = compile_hypothesis(
        root=tmp_path, report=reports[0], write=False, use_model=False,
    )

    diagnosis = enrich_diagnosis({"failure_class": "executable_sample_contract"}, compilation)

    assert diagnosis["hypothesis_compiler_status"] == "compiled"
    assert diagnosis["compiled_hypotheses"][0]["authority"] == "hypothesis_only"
    assert "proposed_knowledge" not in diagnosis


def test_existing_corpus_compilation_deduplicates_clusters(tmp_path):
    reports = [_report(name) for name in ("one", "two", "three")]
    _write_history(tmp_path, reports)

    result = compile_existing_evidence(root=tmp_path, write=False, use_model=False)

    assert result["source_report_count"] == 3
    assert result["cluster_count"] == 1
    assert result["compiled_hypothesis_count"] == 1


def test_model_request_stays_within_local_context_budget():
    cluster = {
        "failure_class": "executable_sample_contract",
        "portable_signature": "meta_only|pure|return_expression",
        "semantic_context": ["executable_failure:receiver_materialization_mismatch"],
        "positive_cases": [_report(f"project_{index}") for index in range(12)],
        "counterexamples": [_report(f"control_{index}") for index in range(3)],
    }

    request = _synthesis_request(cluster)

    assert len(json.dumps(request, ensure_ascii=False)) < 6000
    assert "plugin_outcomes" not in json.dumps(request)
