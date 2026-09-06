from runtime.narrow_type_role_semantics import evaluate_narrow_type_role_semantics


ROLES = (
    "project_analyzer", "architect", "spec_writer",
    "implementer", "tester", "reviewer",
)


def _case(project: str, stratum: str, lineage: str) -> dict:
    target = "src/demo.py:normalize"
    issue = {"evidence": [f"failing_test:{target}"], "affected_targets": [target]}
    artifacts = {
        "project_map_report": {
            "summary": {"root": "demo"}, "answers": {"1_scope": {}},
            "source_health": {"status": "clean"},
        },
        "architecture_decision": {
            "artifact_type": "ArchitectureDecisionRecord", "status": "ok",
            "first_slice_contract": {"targets": [target]},
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
        lambda _value: {"role_scores": {role: 10.0 for role in ROLES}},
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
        lambda _value: {"role_scores": {role: 10.0 for role in ROLES}},
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
        lambda _value: {"role_scores": {role: 10.0 for role in ROLES}},
    )
    cases = _cases()
    cases[0]["execution_run"]["experiment"]["project_native_verification"]["regression_suite"]["status"] = "failed"
    cases[0]["role_run"]["role_artifacts"].pop("technical_spec")

    result = evaluate_narrow_type_role_semantics(cases=cases, evaluation_split="holdout")

    assert result["status"] == "evidence_required"
    assert result["role_scores"]["spec_writer"] < 9.7
    assert result["role_scores"]["tester"] < 9.7
    assert result["checks"]["all_role_artifacts_auditable"] is False
