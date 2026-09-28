from runtime.role_project_type_cases import _github_full_chain_evaluation_case


def test_github_full_chain_case_scores_only_verified_role_boundaries() -> None:
    case = _github_full_chain_evaluation_case({
        "project": "owner__plugin",
        "status": "ok",
        "failed_checks": [],
        "project_classification": {"project_stratum": "framework_plugin_build"},
        "project_recognition": {"status": "recognized"},
        "artifact_status": {
            "architecture_decision": "ArchitectureDecisionRecord",
            "technical_spec": "TechnicalSpec",
            "implementation_plan": "ImplementationPlan",
            "test_plan": "TestPlan",
            "review_findings": "ReviewFindings",
        },
        "target_chain": {
            "spec_target": "module.py:value",
            "implementation_target": "module.py:value",
            "test_target": "module.py:value",
            "review_target": "module.py:value",
        },
        "conformance_status": "passed",
        "contract_violations": 0,
        "architecture_drift": 0,
        "executor": {
            "executor_status": "ok",
            "executable_acceptance": "passed",
            "callable_harness_count": 1,
            "source_code_changes": False,
        },
        "generated_function_stub_admission": {"status": "passed"},
        "role_semantic_quality": {
            "status": "passed",
            "role_scores": {
                "project_analyzer": 9.7,
                "architect": 9.8,
                "spec_writer": 9.9,
            },
        },
    })

    assert set(case["role_scores"]) == {
        "project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer"
    }
    assert case["source_lineage"] == "github_owner:owner"


def test_github_full_chain_case_does_not_invent_scores_from_artifact_presence() -> None:
    case = _github_full_chain_evaluation_case({
        "project": "owner__plugin",
        "status": "ok",
        "project_recognition": {"status": "recognized"},
        "artifact_status": {"architecture_decision": "ArchitectureDecisionRecord"},
    })

    assert case["role_scores"] == {}
