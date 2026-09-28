from __future__ import annotations

from tests.runtime.role_project_type_evaluation_helpers import *

def test_validated_project_development_run_becomes_one_native_transformation_case() -> None:
    case = _project_development_evaluation_case({
        "artifact_type": "ProjectDevelopmentRun",
        "project": "platformdirs",
        "status": "experiment_validated",
        "recognition": {
            "status": "recognized",
            "classification": {
                "schema_version": "role_project_classification.v1",
                "policy_version": load_role_project_type_policy()["classification_version"],
                "project_stratum": "library_pure_transform",
            },
        },
        "role_chain_handoff": {"status": "completed_aligned", "issue_target_aligned": True},
        "decision": {"selected_issue": {
            "failure_kinds": ["missing_registry_value"],
        }},
        "experiment": {
            "status": "verified",
            "selected_target": "src/platformdirs/windows.py:get_win_folder_from_registry",
            "patch_kinds": ["fallback_missing_registry_to_env"],
            "source_invariant": {"unchanged": True},
            "project_native_verification": {
                "status": "passed",
                "authority": "project_native_pytest",
                "targeted_replay": {"status": "passed"},
                "regression_suite": {"status": "passed"},
            },
        },
        "outcome_reassessment": {"status": "validated"},
    })

    assert case["programmer_evidence"]["transformation_evaluated"] is True
    assert case["role_scores"]["tester"] == 10.0
    assert case["source_lineage"] == "project_native_failure:missing_registry_value"


def test_policy_classifies_archetype_and_cross_cutting_risks() -> None:
    policy = load_role_project_type_policy()

    classified = classify_project_case(
        {
            "project": "jobs",
            "artifacts": {
                "project_map_report": {
                    "domain_profile": {"kind": "async_worker_queue"},
                    "answers": {"execution": "HTTP provider job queue with retry state"},
                },
                "technical_spec": {
                    "extraction_contract": {
                        "side_effect_policy": {
                            "network": "provider API is fixture-backed",
                            "state": "retry lifecycle is explicit",
                        }
                    }
                },
            },
        },
        policy=policy,
    )

    assert classified["project_stratum"] == "async_worker_scheduler"
    assert classified["project_archetype"] == "async_worker_queue"
    assert {"concurrent", "network", "provider_llm", "stateful"} <= set(classified["risk_profiles"])


def test_known_pure_library_gets_policy_default_deterministic_risk() -> None:
    classified = classify_project_case({
        "project": "normalizer",
        "artifacts": {"project_map_report": {"domain_profile": {"kind": "schema_validation_library"}}},
    })

    assert classified["project_stratum"] == "library_pure_transform"
    assert classified["risk_profiles"] == ["deterministic"]


def test_project_map_effects_distinguish_pure_cli_from_stateful_filesystem_cli() -> None:
    def classify(effects):
        return classify_project_case({
            "project": "terminal-tool",
            "artifacts": {"project_map_report": {
                "domain_profile": {"kind": "terminal_rendering_library"},
                "answers": {
                    "2_execution": {"central_flow_nodes": [
                        {"path": "tool.py", "name": "run", "side_effects": effects},
                    ]},
                    "3_capabilities": {"pure_transforms": [
                        {"path": "tool.py", "name": "normalize"},
                    ]},
                },
            }},
        })

    pure = classify([])
    read_only = classify(["filesystem_read"])
    stateful = classify(["filesystem", "memory_state"])

    assert pure["risk_profiles"] == ["deterministic"]
    assert "filesystem" in read_only["risk_profiles"]
    assert {"deterministic", "filesystem", "stateful"} <= set(stateful["risk_profiles"])


def test_source_backed_archetype_wins_and_exposes_project_name_conflict() -> None:
    classified = classify_project_case({
        "project": "athina-sdk",
        "artifacts": {"project_map_report": {"domain_profile": {"kind": "docs_site_generator"}}},
    })

    assert classified["project_stratum"] == "framework_plugin_build"
    assert classified["project_name_stratum"] == "sdk_provider_integration"
    assert classified["classification_conflict"] is True


def test_unknown_authoritative_archetype_cannot_be_hidden_by_project_name() -> None:
    classified = classify_project_case({
        "project": "mystery-cli",
        "archetype": "event_log_projection",
    })

    assert classified["project_stratum"] == "unknown_new_archetype"
    assert classified["project_name_stratum"] == "cli_local_tool"
    assert classified["classification_conflict"] is True
    assert classified["classification_source"] == "fallback_authoritative_unmatched"


def test_stale_unversioned_classification_is_recomputed_from_project_map() -> None:
    classified = classify_project_case({
        "project": "bokeh",
        "project_classification": {"project_stratum": "workspace_portfolio"},
        "artifacts": {
            "project_map_report": {
                "content": {
                    "answers": {"1_scope": {"domain_profile": {"kind": "visualization_plotting_library"}}},
                    "source_health": {"project_shape": "multi_project_workspace"},
                }
            }
        },
    })

    assert classified["project_stratum"] == "data_tabular_pipeline"
    assert classified["schema_version"] == "role_project_classification.v1"


def test_stale_policy_version_is_recomputed_after_classification_policy_changes() -> None:
    classified = classify_project_case({
        "project": "aiohttp-runtime",
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": "role_project_classification.older",
            "project_stratum": "unknown_new_archetype",
        },
        "artifacts": {
            "project_map_report": {
                "domain_profile": {"kind": "async_protocol_runtime"},
            }
        },
    })

    assert classified["project_stratum"] == "async_worker_scheduler"
    assert classified["policy_version"] == load_role_project_type_policy()["classification_version"]


def test_current_unknown_classification_is_recomputed_when_archetype_becomes_known() -> None:
    policy = load_role_project_type_policy()
    classified = classify_project_case({
        "project": "camera-counter",
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": policy["classification_version"],
            "project_stratum": "unknown_new_archetype",
            "project_archetype": "computer_vision_tracking_application",
        },
    }, policy=policy)

    assert classified["project_stratum"] == "ml_inference"
    assert classified["classification_source"] == "evidence_match"


def test_legacy_compatible_classification_remains_authoritative() -> None:
    classified = classify_project_case({
        "project": "derived-cli-case",
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": "role_project_classification.2026-08-26.5",
            "project_stratum": "cli_local_tool",
        },
    })

    assert classified["project_stratum"] == "cli_local_tool"
    assert classified["classification_source"] == "explicit"


def test_legacy_removed_data_stratum_is_reclassified_to_specific_scope() -> None:
    classified = classify_project_case({
        "project": "scientific-project",
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": "role_project_classification.2026-08-26.5",
            "project_stratum": "data_scientific_ml",
            "project_archetype": "scientific_compute_library",
        },
    })

    assert classified["project_stratum"] == "scientific_compute"


def test_data_ml_archetypes_are_split_into_independent_strata() -> None:
    expectations = {
        "dataframe_pipeline": "data_tabular_pipeline",
        "scientific_compute_library": "scientific_compute",
        "model_inference_runtime": "ml_inference",
        "computer_vision_tracking_application": "ml_inference",
        "reinforcement_learning": "ml_training_checkpoint",
    }

    for archetype, expected in expectations.items():
        classified = classify_project_case({
            "project": archetype,
            "artifacts": {"project_map_report": {"domain_profile": {"kind": archetype}}},
        })
        assert classified["project_stratum"] == expected


def test_specific_llm_archetype_outranks_generic_provider_marker() -> None:
    classified = classify_project_case({
        "project": "nexus-sdk",
        "artifacts": {
            "project_map_report": {
                "domain_profile": {"kind": "llm_provider_gateway"},
            }
        },
    })

    assert classified["project_stratum"] == "llm_multi_agent"


def test_signing_archetype_outranks_generic_token_utility_marker() -> None:
    classified = classify_project_case({
        "project": "itsdangerous",
        "artifacts": {
            "project_map_report": {
                "domain_profile": {"kind": "signing_token_utility"},
            }
        },
    })

    assert classified["project_stratum"] == "external_process_io"


def test_specific_stateful_contract_outranks_broad_web_archetype() -> None:
    classified = classify_project_case({
        "project": "diskcache",
        "artifacts": {
            "project_map_report": {
                "domain_profile": {"kind": "asgi_wsgi_server_runtime"},
            },
            "technical_spec": {
                "extraction_contract": {"contract_family": "cache_key_value_operation"},
            },
        },
    })

    assert classified["project_stratum"] == "stateful_service_database"


def test_bounded_dataframe_contract_outranks_repository_compute_archetype() -> None:
    classified = classify_project_case({
        "project": "data-library",
        "selected_candidate_quality": {
            "structural_evidence": {"observed_side_effects": []},
        },
        "architect_first_slice": {
            "notes": "The wider repository may use subprocess workers and concurrent execution.",
        },
        "artifacts": {
            "project_map_report": {
                "domain_profile": {"kind": "distributed_compute_graph"},
            },
            "technical_spec": {
                "extraction_contract": {
                    "contract_family": "dataframe_conversion_boundary",
                    "side_effect_policy": {
                        "declared": [],
                        "process_boundary_recommended": False,
                    },
                },
            },
        },
    })

    assert classified["project_stratum"] == "data_tabular_pipeline"
    assert classified["classification_source"] == "contract_family_precedence"
    assert "subprocess" not in classified["risk_profiles"]
    assert "concurrent" not in classified["risk_profiles"]


def test_known_compound_cache_tokens_match_without_substring_matching() -> None:
    for project in ("packages__aiocache", "packages__aiomcache"):
        classified = classify_project_case({"project": project})

        assert classified["project_stratum"] == "stateful_service_database"
        assert classified["project_name_stratum"] == "stateful_service_database"


def test_marker_matching_does_not_treat_orm_as_part_of_transform() -> None:
    classified = classify_project_case({
        "project": "logging-tree",
        "selected_candidate_quality": {"selection_evidence": {"kind": "orm_relation"}},
        "artifacts": {
            "project_map_report": {
                "content": {"answers": {"1_scope": {"domain_profile": {"kind": "pure_transform"}}}}
            }
        },
    })

    assert classified["project_stratum"] == "library_pure_transform"


def test_evaluation_uses_worst_case_and_requires_independent_blind_evidence(tmp_path: Path) -> None:
    ordinary = tmp_path / "ordinary.json"
    blind = tmp_path / "blind.json"
    ordinary.write_text(
        json.dumps({"cases": [_case(f"cli-{index}", 9.6, 7.2) for index in range(3)]}),
        encoding="utf-8",
    )
    blind.write_text(
        json.dumps({"cases": [_case(f"cli-blind-{index}", 9.3, 7.8) for index in range(2)]}),
        encoding="utf-8",
    )

    report = build_role_project_type_evaluation(
        root=tmp_path,
        report_paths=[ordinary, blind],
        blind_report_paths=[blind],
    )

    analyzer = _cell(report, "project_analyzer", "cli_local_tool")
    implementer = _cell(report, "implementer", "cli_local_tool")
    researcher = _cell(report, "researcher", "cli_local_tool")
    assert analyzer["score"] == 9.3
    assert analyzer["maturity"] == "mature"
    assert analyzer["confidence"] == "high"
    assert analyzer["promotion_eligible"] is False
    assert analyzer["promotion_status"] == "score_below_promotion_target"
    assert analyzer["promotion_target_score"] == 9.7
    assert implementer["score"] == 7.2
    assert implementer["maturity"] == "weak"
    assert researcher["maturity"] == "not_applicable"
    assert report["priority_queue"][0]["role_id"] == "implementer"
