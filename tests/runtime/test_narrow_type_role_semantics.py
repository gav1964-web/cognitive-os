from runtime.narrow_type_role_semantics import evaluate_narrow_type_role_semantics


ROLES = (
    "project_analyzer", "architect", "spec_writer",
    "implementer", "tester", "reviewer",
)


def _case(project: str, stratum: str, lineage: str) -> dict:
    target = "src/demo.py:normalize"
    issue = {
        "evidence": [f"failing_test:{target}"],
        "affected_targets": [target],
        "failure_evidence": [{
            "detail": "AssertionError: whitespace was retained",
            "failure_signature": "known-signature",
            "failing_nodeids": ["tests/test_demo.py::test_normalize"],
        }],
        "causal_hypothesis": {
            "mechanism": "The input reaches the return path before surrounding whitespace is removed.",
            "evidence": [target, "tests/test_demo.py::test_normalize"],
        },
    }
    artifacts = {
        "project_map_report": {
            "summary": {"root": "demo"}, "answers": {"1_scope": {}},
            "source_health": {"status": "clean"},
        },
        "architecture_decision": {
            "artifact_type": "ArchitectureDecisionRecord", "status": "ok",
            "first_slice_contract": {"targets": [target]},
            "repair_design": {
                "target": target,
                "mechanism": "Normalize surrounding whitespace at the bounded function return path.",
                "evidence": [target, "tests/test_demo.py::test_normalize"],
            },
        },
        "technical_spec": {
            "artifact_type": "TechnicalSpec", "status": "ok",
            "extraction_contract": {"candidate": target},
            "requirements": [
                {"id": f"REQ-{index}", "statement": f"Requirement {index} preserves normalization", "target": target}
                for index in range(3)
            ],
            "acceptance_criteria": [
                {"id": f"AC-{index}", "criterion": f"Regression check {index} passes"}
                for index in range(3)
            ],
            "traceability_table": [
                {"acceptance_id": f"AC-{index}", "requirement_id": f"REQ-{index}", "target": target}
                for index in range(3)
            ],
            "verification_strategy": {
                "regression_checks": [{"target": target, "assertion": "suite passes"}],
            },
            "implementation_delta": {
                "status": "ready",
                "intent": {
                    "target_symbol": target,
                    "operator_id": "strip_surrounding_whitespace",
                    "mutation": "Strip surrounding whitespace before returning the normalized value.",
                },
            },
        },
    }
    role_run = {
        "project": project,
        "recognition": {
            "status": "recognized",
            "classification": {"effective_project_identity": stratum},
            "evidence": {"project_analyzer_evidence": ["source marker"]},
        },
        "decision": {"selected_issue": issue},
        "role_chain_handoff": {
            "status": "completed_aligned", "issue_target_aligned": True,
            "selected_target": target,
        },
        "role_artifacts": artifacts,
    }
    execution_run = {
        "project": project,
        "status": "experiment_validated",
        "role_chain_handoff": {"selected_target": target},
        "experiment": {
            "status": "verified", "apply_source": False, "patch_count": 1,
            "patch_synthesis_status": "prepared",
            "checks": {
                "executor_completed": True, "no_generated_function_stubs": True,
                "verification_passed": True,
            },
            "project_native_verification": {
                "status": "passed",
                "targeted_replay": {"status": "passed"},
                "regression_suite": {"status": "passed"},
            },
            "source_invariant": {"unchanged": True},
            "generated_function_stub_admission": {"status": "passed"},
        },
    }
    return {
        "project": project, "project_stratum": stratum,
        "source_lineage": lineage, "source_owner": lineage, "role_run": role_run,
        "execution_run": execution_run,
    }


def _cases() -> list[dict]:
    return [
        _case("cli-a", "cli_local_tool", "owner-a"),
        _case("cli-b", "cli_local_tool", "owner-b"),
        _case("lib-a", "library_pure_transform", "owner-c"),
        _case("lib-b", "library_pure_transform", "owner-d"),
    ]


def test_semantic_evidence_requires_real_artifacts_and_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value, **_kwargs: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    result = evaluate_narrow_type_role_semantics(
        cases=_cases(), evaluation_split="holdout"
    )

    assert result["status"] == "passed"
    assert min(result["role_scores"].values()) == 10.0
    assert result["checks"]["independent_lineages_per_stratum"] is True
    assert result["checks"]["holdout_independent_owners_per_stratum"] is True


def test_holdout_requires_independent_source_owners(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value, **_kwargs: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    cases = _cases()
    cases[0]["source_owner"] = "shared-owner"
    cases[1]["source_owner"] = "shared-owner"

    result = evaluate_narrow_type_role_semantics(
        cases=cases, evaluation_split="holdout"
    )

    assert result["status"] == "evidence_required"
    assert result["checks"]["independent_lineages_per_stratum"] is True
    assert result["checks"]["holdout_independent_owners_per_stratum"] is False


def test_semantic_evidence_rejects_missing_regression_and_artifact(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value, **_kwargs: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    cases = _cases()
    cases[0]["execution_run"]["experiment"]["project_native_verification"]["regression_suite"]["status"] = "failed"
    cases[0]["role_run"]["role_artifacts"].pop("technical_spec")

    result = evaluate_narrow_type_role_semantics(cases=cases, evaluation_split="holdout")

    assert result["status"] == "evidence_required"
    assert result["role_scores"]["spec_writer"] < 9.7
    assert result["role_scores"]["tester"] < 9.7
    assert result["checks"]["all_role_artifacts_auditable"] is False


def test_project_analyzer_score_requires_expected_archetype_match(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value, **_kwargs: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    cases = _cases()
    cases[0]["expected_project_archetype"] = "test_framework_library"
    cases[0]["role_run"]["recognition"]["classification"]["project_archetype"] = "async_worker_queue"

    result = evaluate_narrow_type_role_semantics(cases=cases, evaluation_split="holdout")

    assert result["status"] == "evidence_required"
    assert result["cases"][0]["checks"]["project_analyzer"]["project_archetype_matches_ground_truth"] is False
    assert result["role_scores"]["project_analyzer"] < 9.7


def test_structurally_complete_roles_are_capped_without_causal_repair_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value, **_kwargs: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    cases = _cases()
    for case in cases:
        issue = case["role_run"]["decision"]["selected_issue"]
        issue.pop("causal_hypothesis")
        artifacts = case["role_run"]["role_artifacts"]
        artifacts["architecture_decision"].pop("repair_design")
        artifacts["technical_spec"]["implementation_delta"] = {
            "status": "semantic_synthesis_required"
        }
        case["execution_run"]["status"] = "research_required"
        case["execution_run"]["experiment"] = {"status": "blocked", "apply_source": False}

    result = evaluate_narrow_type_role_semantics(cases=cases, evaluation_split="holdout")

    assert result["role_scores"]["project_analyzer"] == 8.0
    assert result["role_scores"]["architect"] == 6.0
    assert result["role_scores"]["spec_writer"] == 6.0
    assert result["cases"][0]["structural_role_scores"]["project_analyzer"] > 8.0
    assert "missing_causal_diagnosis" in {
        row["reason"] for row in result["cases"][0]["score_caps_applied"]["project_analyzer"]
    }


def test_training_replay_cannot_claim_transfer_maturity(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.narrow_type_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value, **_kwargs: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    cases = _cases()
    cases[0]["regression_scope_kind"] = "affected_subsystem"

    result = evaluate_narrow_type_role_semantics(
        cases=cases, evaluation_split="training_replay"
    )

    assert result["status"] == "evidence_required"
    assert result["role_scores"] == {
        "project_analyzer": 9.4,
        "architect": 8.5,
        "spec_writer": 8.5,
        "implementer": 8.8,
        "tester": 8.5,
        "reviewer": 8.5,
    }
    assert "training_replay" in {
        row["reason"] for row in result["cases"][1]["score_caps_applied"]["architect"]
    }
