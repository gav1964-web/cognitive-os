from __future__ import annotations

from tests.runtime.project_development_helpers import *

def test_memory_rejects_outcome_that_bypassed_pilot_stop(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    prior = {
        "project_root": project.resolve().as_posix(),
        "validated_memory": {"status": "validated", "authority": "verified_sandbox_outcome"},
        "recognition": {"pilot_route": {"status": "analysis_only_stop"}},
    }

    memory = _memory_context(project, [prior])

    assert memory["validated_memory_count"] == 0
    assert memory["rejected_validated_memory_count"] == 1


def test_development_loop_prioritizes_evidence_backed_high_issue_and_outcome():
    policy = load_project_development_policy()
    diagnosis = build_development_diagnosis(
        project="demo",
        project_report=_report(),
        recognition={"status": "recognized", "ambiguity_reasons": []},
        policy=policy,
    )
    portfolio = build_development_options(diagnosis, policy=policy)
    decision = select_development_option(diagnosis, portfolio, policy=policy)
    outcome = build_outcome_contract(decision, policy=policy)

    assert diagnosis["issues"][0]["rule_id"] in {"high_project_risk", "weak_contracts"}
    assert decision["status"] == "selected"
    assert decision["selected_option"]["route"] == "role_chain"
    assert outcome["status"] == "defined"
    assert "regression_suite_passed" in outcome["required_checks"]


def test_uncorroborated_weak_contract_zones_are_observations_not_issues():
    diagnosis = build_development_diagnosis(
        project="typed-style-choice",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [],
            "answers": {"4_contracts_data": {"weak_contract_zones": ["pkg/helpers.py:normalize"]}},
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        policy=load_project_development_policy(),
    )

    assert diagnosis["status"] == "no_actionable_issue"
    assert diagnosis["issues"] == []
    assert diagnosis["observations"]["weak_contract_zones"] == ["pkg/helpers.py:normalize"]
    assert diagnosis["observations"]["actionable_contract_failures"] == []


def test_source_stub_observation_does_not_create_issue_without_failure():
    diagnosis = build_development_diagnosis(
        project="stub-observation",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [],
            "answers": {},
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        source_incompleteness={
            "status": "observations_only",
            "findings": [{
                "target": "pkg/service.py:run",
                "classification": "ambiguous_stub",
                "actionable": False,
            }],
            "actionable_findings": [],
        },
        policy=load_project_development_policy(),
    )

    assert diagnosis["status"] == "no_actionable_issue"
    assert diagnosis["observations"]["source_incompleteness"]["findings"]


def test_structural_and_medium_risk_signals_need_corroboration():
    diagnosis = build_development_diagnosis(
        project="mature-tool",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [{"code": "risky_imports", "severity": "medium", "detail": "subprocess"}],
            "answers": {
                "4_contracts_data": {"weak_contract_zones": []},
                "6_runtime_extraction_readiness": {
                    "mixed_responsibility_functions": [{
                        "path": "pkg/runner.py", "name": "run", "loc": 180,
                    }],
                },
            },
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        policy=load_project_development_policy(),
    )

    assert diagnosis["status"] == "no_actionable_issue"
    assert diagnosis["observations"]["mixed_responsibility_functions"]
    assert diagnosis["observations"]["medium_project_risks"]


def test_security_shaped_high_risk_needs_scanner_or_failure_authority():
    diagnosis = build_development_diagnosis(
        project="auth-tool",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [{
                "code": "secret_material_in_source",
                "severity": "high",
                "detail": "auth/store.py and oauth.py",
            }],
            "answers": {},
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        policy=load_project_development_policy(),
    )

    assert diagnosis["status"] == "no_actionable_issue"
    assert diagnosis["observations"]["high_project_risks"][0]["code"] == "secret_material_in_source"


def test_scanner_corroborated_high_risk_is_actionable():
    diagnosis = build_development_diagnosis(
        project="leaking-tool",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [{
                "code": "secret_material_in_source",
                "severity": "high",
                "detail": "scanner found a committed token",
                "authority": "security_scanner_finding",
            }],
            "answers": {},
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        policy=load_project_development_policy(),
    )

    assert diagnosis["issues"][0]["rule_id"] == "high_project_risk"


def test_failure_kind_limits_project_development_to_matching_reducer():
    diagnosis = build_development_diagnosis(
        project="platformdirs",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [],
            "answers": {},
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        chain_case={
            "contract_failure_evidence": [{
                "target": "src/platformdirs/windows.py:get_win_folder_from_registry",
                "authority": "failing_contract_test",
                "detail": "FileNotFoundError",
                "failure_kind": "missing_registry_value",
                "failing_nodeids": ["tests/test_api.py::test_no_ctypes[user_data_dir]"],
            }],
        },
        policy=load_project_development_policy(),
    )

    issue = diagnosis["issues"][0]
    assert issue["failure_kinds"] == ["missing_registry_value"]
    assert issue["allowed_operator_ids"] == ["fallback_missing_registry_to_env"]
    assert "insert_required_input_guard" not in issue["allowed_operator_ids"]
    assert issue["failure_evidence"][0]["failing_nodeids"] == [
        "tests/test_api.py::test_no_ctypes[user_data_dir]"
    ]


def test_failure_repair_transform_binds_effectful_target_without_extraction_rerank():
    decision = {
        "selected_issue": {
            "rule_id": "weak_contracts",
            "affected_targets": ["src/platformdirs/windows.py:get_win_folder_from_registry"],
            "failure_kinds": ["missing_registry_value"],
            "allowed_operator_ids": ["fallback_missing_registry_to_env"],
            "failure_specific_reducer_required": True,
            "failure_evidence": [{
                "target": "src/platformdirs/windows.py:get_win_folder_from_registry",
                "authority": "failing_contract_test",
                "failure_kind": "missing_registry_value",
                "failing_nodeids": ["tests/test_api.py::test_no_ctypes[user_data_dir]"],
            }],
        },
        "selected_option": {"option_id": "OPTION-001"},
    }
    transform = development_delta_transform(decision, load_project_development_policy())
    spec = transform({
        "artifact_type": "TechnicalSpec",
        "source_evidence": [{
            "source": "src/platformdirs/windows.py:get_win_folder_from_registry",
            "signature": {"args": [{"name": "csidl_name", "annotation": "str"}], "returns": "str"},
            "snippet": "def get_win_folder_from_registry(csidl_name: str) -> str:\n    return csidl_name",
        }],
        "acceptance_criteria": [
            {"id": f"OLD-{index}", "criterion": "generic", "verification": "review"}
            for index in range(30)
        ],
        "implementation_handoff": {},
    })

    contract = spec["extraction_contract"]
    assert contract["mode"] == "failure_repair"
    assert contract["candidate"] == "src/platformdirs/windows.py:get_win_folder_from_registry"
    assert contract["allowed_operator_ids"] == ["fallback_missing_registry_to_env"]
    assert spec["first_slice_reselection_request"]["status"] == "not_required"
    assert spec["acceptance_criteria"][0]["authority"] == "failing_contract_test"
    assert len(spec["acceptance_criteria"]) == 3
    assert spec["acceptance_criteria"][1]["id"] == "AC-FAILURE-BOUNDARY"
    assert spec["acceptance_criteria"][2]["id"] == "AC-FAILURE-REGRESSION"
    assert {row["target"] for row in spec["requirements"]} == {contract["candidate"]}
    assert {row["acceptance_id"] for row in spec["traceability_table"]} == {
        row["id"] for row in spec["acceptance_criteria"]
    }
    assert all(
        row["target"] == contract["candidate"]
        for rows in spec["verification_strategy"].values()
        for row in rows
    )


def test_failure_repair_transform_preserves_research_target_without_reducer():
    decision = {
        "selected_issue": {
            "rule_id": "weak_contracts",
            "affected_targets": ["src/plugin.py:Server.start"],
            "allowed_operator_ids": [],
            "failure_specific_reducer_required": True,
            "failure_evidence": [{
                "target": "src/plugin.py:Server.start",
                "authority": "failing_contract_test",
                "failure_kind": "server_start_readiness_cleanup_contract",
                "failing_nodeids": ["tests/test_plugin.py::test_readiness_failure"],
            }],
        },
        "selected_option": {"option_id": "OPTION-001"},
    }
    transform = development_delta_transform(decision, load_project_development_policy())

    spec = transform({
        "artifact_type": "TechnicalSpec",
        "source_evidence": [{
            "source": "src/plugin.py:Server.start",
            "signature": {"args": [{"name": "self"}], "returns": "None"},
            "snippet": "def start(self):\n    self.running = True",
        }],
        "acceptance_criteria": [],
        "implementation_handoff": {},
    })

    assert spec["extraction_contract"]["candidate"] == "src/plugin.py:Server.start"
    assert spec["extraction_contract"]["allowed_operator_ids"] == []
    assert spec["extraction_contract"]["side_effects"]["declared"]
    assert spec["extraction_contract"]["side_effects"]["requires_validation_gate"] is True
    assert spec["implementation_delta"]["status"] == "semantic_synthesis_required"
    assert spec["implementation_handoff"]["patch_scope"] == ["src/plugin.py:Server.start"]


def test_failure_repair_contract_uses_structural_input_shapes():
    decision = {
        "selected_issue": {
            "rule_id": "weak_contracts",
            "affected_targets": ["src/demo.py:split_before"],
            "allowed_operator_ids": [],
            "failure_specific_reducer_required": True,
            "failure_evidence": [{
                "target": "src/demo.py:split_before",
                "authority": "failing_contract_test",
                "failing_nodeids": ["tests/test_demo.py::test_empty"],
            }],
        },
        "selected_option": {"option_id": "OPTION-001"},
    }
    spec = development_delta_transform(decision, load_project_development_policy())({
        "artifact_type": "TechnicalSpec",
        "source_evidence": [{
            "source": "src/demo.py:split_before",
            "signature": {"args": [{"name": "values", "annotation": ""}], "returns": ""},
            "snippet": "def split_before(values):\n    for value in iter(values):\n        yield value",
        }],
        "implementation_handoff": {},
    })

    assert spec["extraction_contract"]["input_contract"] == {"values": "IterableLike"}
    assert spec["extraction_contract"]["output_contract"] == {"result": "IteratorLike"}


def test_focused_report_uses_affected_target_not_authority_prefixed_evidence():
    focused = _focused_project_report(
        {"summary": {}, "answers": {}},
        {
            "issue_id": "ISSUE-001",
            "rule_id": "weak_contracts",
            "evidence": ["failing_contract_test:src/platformdirs/windows.py:get_win_folder_from_registry"],
            "affected_targets": ["src/platformdirs/windows.py:get_win_folder_from_registry"],
        },
        {"strategy": "contract_characterization"},
    )

    context = focused["project_development_context"]
    assert context["allowed_targets"] == ["src/platformdirs/windows.py:get_win_folder_from_registry"]
    assert focused["architecture_synthesis"]["recommended_first_slice"]["targets"] == context["allowed_targets"]


def test_corroborated_architecture_finding_is_actionable():
    diagnosis = build_development_diagnosis(
        project="measured-bottleneck",
        project_report={
            "source_health": {"status": "clean", "project_shape": "single_project"},
            "risks": [],
            "answers": {
                "6_runtime_extraction_readiness": {
                    "mixed_responsibility_functions": [{
                        "path": "pkg/runner.py",
                        "name": "run",
                        "authority": "measured_runtime_bottleneck",
                    }],
                },
            },
        },
        recognition={"status": "recognized", "ambiguity_reasons": []},
        policy=load_project_development_policy(),
    )

    assert diagnosis["issues"][0]["rule_id"] == "mixed_responsibility"


def test_unknown_project_routes_to_research_before_role_chain():
    policy = load_project_development_policy()
    diagnosis = build_development_diagnosis(
        project="unknown",
        project_report={"source_health": {"status": "clean", "project_shape": "single_project"}, "risks": [], "answers": {}},
        recognition={"status": "unknown", "ambiguity_reasons": ["no_configured_project_stratum_matched"]},
        policy=policy,
    )
    portfolio = build_development_options(diagnosis, policy=policy)
    decision = select_development_option(diagnosis, portfolio, policy=policy)

    assert decision["selected_issue"]["rule_id"] == "recognition_gap"
    assert decision["selected_option"]["route"] == "research"


def test_blocked_chain_case_becomes_explicit_development_issue():
    policy = load_project_development_policy()
    diagnosis = build_development_diagnosis(
        project="blocked",
        project_report={"source_health": {"status": "clean", "project_shape": "single_project"}, "risks": [], "answers": {}},
        recognition={"status": "recognized", "ambiguity_reasons": []},
        chain_case={"binding_status": "blocked_no_safe_candidate", "target_chain": {"adr_targets": ["pkg/app.py:run"]}},
        policy=policy,
    )

    assert any(row["rule_id"] == "no_safe_candidate" for row in diagnosis["issues"])


def test_role_handoff_alignment_requires_issue_source_identity():
    assert _target_issue_aligned("pkg/service.py:run", ["pkg/service.py:run"])
    assert _target_issue_aligned("pkg/service.py:helper", ["pkg/service.py:run"])
    assert not _target_issue_aligned("pkg/unrelated.py:helper", ["pkg/service.py:run"])


def test_development_decision_focuses_architect_first_slice_on_issue_targets():
    focused = _focused_project_report(
        {"summary": {"entrypoints": ["main.py"], "languages": ["Python"]}, "answers": {"1_scope": {"domain_profile": {"kind": "python_project"}}}},
        {"issue_id": "ISSUE-001", "rule_id": "weak_contracts", "confidence": 0.9, "evidence": ["pkg/service.py:run", "risk:ignored"]},
        {"strategy": "contract_characterization"},
    )

    assert focused["architecture_synthesis"]["recommended_first_slice"]["targets"] == ["pkg/service.py:run"]


def test_sandbox_patch_scope_must_stay_inside_selected_issue_files():
    evidence = ["pkg/service.py:run"]

    assert _patch_scope_aligned({"patches": [{"file": "pkg/service.py"}]}, evidence)
    assert not _patch_scope_aligned({"patches": [{"file": "pkg/unrelated.py"}]}, evidence)
    assert not _patch_scope_aligned({"patches": []}, evidence)
