from __future__ import annotations

from pathlib import Path

from runtime.foundation_semantic_quality import evaluate_foundation_semantic_quality
from runtime.foundation_semantic_quality_policy import load_foundation_semantic_quality_policy


ROOT = Path(__file__).resolve().parents[2]


def test_foundation_semantic_quality_policy_loads_current_catalog() -> None:
    policy = load_foundation_semantic_quality_policy(str(ROOT / "config" / "foundation_semantic_quality_policy.json"))

    assert policy["schema_version"] == "foundation_semantic_quality_policy.v1"
    assert policy["spec_writer"]["minimum_requirements"] >= 3
    assert "best practices" in policy["specific_text"]["generic_phrases"]


def test_foundation_semantic_quality_uses_configured_specific_text_policy() -> None:
    policy = load_foundation_semantic_quality_policy(str(ROOT / "config" / "foundation_semantic_quality_policy.json"))
    policy = {
        **policy,
        "specific_text": {
            **policy["specific_text"],
            "min_length": 8,
            "generic_phrases": ["forbidden-custom-generic"],
        },
    }
    report = {
        "artifacts": {
            "project_map_report": {
                "summary": {"root": "demo", "file_count": 1, "frameworks": [], "entrypoints": []},
                "answers": {
                    "1_scope": {
                        "main_task": "Tiny but now long enough",
                        "supported_scenarios": ["run", "validate"],
                        "inputs": ["CLI args"],
                        "outputs": ["stdout"],
                        "domain_profile": {"kind": "generic", "confidence": 0.0, "evidence": []},
                    },
                    "2_execution": {"primary_execution_path": ["main.py:main"]},
                    "3_capabilities": {"atomic_reusable_capabilities": ["main.py:main"]},
                    "4_contracts_data": {"main_data_structures": ["Args"], "weak_contract_zones": []},
                    "5_errors_state_repro": {
                        "likely_error_types": ["bad input"],
                        "state_to_preserve": ["none"],
                        "minimal_cognitive_loop": ["run", "fail", "report"],
                    },
                    "6_runtime_extraction_readiness": {
                        "data_lifecycle": [{"stage": "input"}, {"stage": "process"}, {"stage": "output"}],
                        "minimal_extraction_plan": {"capabilities_to_extract": [{"capability": "main.py:main", "reason": "bounded CLI entrypoint"}]},
                        "evidence_claims": [
                            {"source": "main.py:1"},
                            {"source": "main.py:2"},
                            {"source": "main.py:3"},
                        ],
                    },
                },
            },
            "architecture_decision": {},
            "technical_spec": {},
        }
    }

    quality = evaluate_foundation_semantic_quality(report, policy=policy)

    assert "project_analyzer.purpose_is_specific" not in quality["warnings"]


def test_foundation_semantic_quality_ignores_badge_urls_as_marketing_noise() -> None:
    policy = load_foundation_semantic_quality_policy(str(ROOT / "config" / "foundation_semantic_quality_policy.json"))
    policy = {**policy, "specific_text": {**policy["specific_text"], "min_length": 16}}
    report = {
        "artifacts": {
            "project_map_report": {
                "summary": {"frameworks": [], "entrypoints": []},
                "answers": {
                    "1_scope": {
                        "main_task": (
                            "Inferred from docs: https://example.test/actions/workflows/test.yml/badge.svg?branch=main "
                            "as a graph algorithm library for node and edge transforms."
                        ),
                        "supported_scenarios": ["run graph algorithm", "return graph result"],
                        "inputs": ["graph"],
                        "outputs": ["cycles"],
                        "domain_profile": {"kind": "graph_algorithm_library", "confidence": 0.7, "evidence": ["networkx"]},
                    },
                    "2_execution": {"primary_execution_path": ["networkx/algorithms/cycles.py:chordless_cycles"]},
                    "3_capabilities": {"atomic_reusable_capabilities": ["networkx/algorithms/cycles.py:chordless_cycles"]},
                    "4_contracts_data": {"main_data_structures": ["Graph"], "weak_contract_zones": []},
                    "5_errors_state_repro": {
                        "likely_error_types": ["invalid graph"],
                        "state_to_preserve": ["graph shape"],
                        "minimal_cognitive_loop": ["input", "traverse", "return"],
                    },
                    "6_runtime_extraction_readiness": {
                        "data_lifecycle": [{"stage": "input"}, {"stage": "traverse"}, {"stage": "return"}],
                        "minimal_extraction_plan": {
                            "capabilities_to_extract": [
                                {"capability": "networkx/algorithms/cycles.py:chordless_cycles", "reason": "bounded graph algorithm"}
                            ]
                        },
                        "evidence_claims": [{"source": "a.py:1"}, {"source": "b.py:2"}, {"source": "c.py:3"}],
                    },
                },
            },
            "architecture_decision": {},
            "technical_spec": {},
        }
    }

    quality = evaluate_foundation_semantic_quality(report, policy=policy)

    assert "project_analyzer.purpose_avoids_marketing_blurb" not in quality["warnings"]


def test_foundation_semantic_quality_allows_profiled_zero_arg_contract() -> None:
    quality = evaluate_foundation_semantic_quality(
        {
            "artifacts": {
                "project_map_report": {
                    "summary": {"root": "demo", "frameworks": [], "entrypoints": ["pkg/core.py"]},
                    "answers": {
                        "1_scope": {
                            "main_task": "Provide certificate bundle resource access for package consumers.",
                            "supported_scenarios": ["read default bundle", "surface missing bundle failure"],
                            "inputs": ["call context"],
                            "outputs": ["certificate bundle text"],
                            "domain_profile": {"kind": "resource_accessor", "confidence": 0.7, "evidence": ["pkg/core.py:contents"]},
                        },
                        "2_execution": {"primary_execution_path": ["pkg/core.py:contents"]},
                        "3_capabilities": {"atomic_reusable_capabilities": ["pkg/core.py:contents"]},
                        "4_contracts_data": {"main_data_structures": ["CertificateBundle"], "weak_contract_zones": []},
                        "5_errors_state_repro": {
                            "likely_error_types": ["missing resource"],
                            "state_to_preserve": ["package resource path"],
                            "minimal_cognitive_loop": ["call", "read", "return"],
                        },
                        "6_runtime_extraction_readiness": {
                            "data_lifecycle": [{"stage": "call"}, {"stage": "resource_read"}, {"stage": "return"}],
                            "minimal_extraction_plan": {
                                "capabilities_to_extract": [{"capability": "pkg/core.py:contents", "reason": "bounded resource accessor"}]
                            },
                            "evidence_claims": [{"source": "pkg/core.py:contents"}, {"source": "pkg/core.py:where"}, {"source": "pkg/core.py:read"}],
                        },
                    },
                },
                "architecture_decision": {
                    "decision_summary": "Select the package resource accessor as the first bounded API slice.",
                    "architecture_synthesis": {
                        "project_profile": {"archetype": "resource_accessor", "domain_profile_kind": "resource_accessor"}
                    },
                    "first_slice_contract": {"name": "resource_accessor_slice", "targets": ["pkg/core.py:contents"]},
                    "architecture_options": [{"id": "resource"}, {"id": "rewrite"}],
                    "rejected_options": [{"id": "rewrite"}],
                    "spec_writer_brief": {
                        "contract_targets": ["pkg/core.py:contents"],
                        "acceptance_targets": ["empty resource and missing resource failures are explicit"],
                        "files_or_symbols": ["pkg/core.py:contents"],
                    },
                    "risks": [{"risk": "resource path drift can break consumers", "mitigation": "contract tests cover missing resource"}],
                    "fact_judgment_ledger": {
                        "facts": [{"claim": "pkg/core.py:contents exists"}],
                        "judgments": [{"judgment": "resource accessor is bounded", "validation_gate": "contract tests"}],
                    },
                    "source_context": {"pkg/core.py:contents": {}, "pkg/core.py:where": {}, "pkg/core.py:read": {}},
                    "open_questions": [],
                    "non_goals": ["Do not rewrite package resource discovery."],
                },
                "technical_spec": {
                    "extraction_contract": {
                        "candidate": "pkg/core.py:contents",
                        "ranked_candidates": [{"source": "pkg/core.py:contents"}],
                        "contract_family": "package_resource_accessor_boundary",
                        "input_contract": {},
                        "output_contract": {"resource_text": "ResourceText"},
                        "side_effects": {"declared": []},
                    },
                    "requirements": [
                        {"statement": "Call pkg/core.py:contents without synthetic payload arguments."},
                        {"statement": "Return the resource payload as text for package consumers."},
                        {"statement": "Report missing or invalid resources as controlled failures."},
                    ],
                    "acceptance_criteria": [
                        {"criterion": "pkg/core.py:contents returns resource text.", "verification": "Run callable acceptance."},
                        {"criterion": "empty resource text is handled explicitly.", "verification": "Run negative fixture."},
                        {"criterion": "missing resource returns controlled error.", "verification": "Run failure fixture."},
                    ],
                    "traceability_table": [
                        {"source": "pkg/core.py:contents", "acceptance_id": "AC-001"},
                        {"source": "pkg/core.py:where", "acceptance_id": "AC-002"},
                        {"source": "pkg/core.py:read", "acceptance_id": "AC-003"},
                    ],
                    "work_plan_contract": {"obligations": ["preserve zero-argument contract"]},
                    "implementation_handoff": {"patch_scope": ["pkg/core.py:contents"]},
                    "human_review": {"decision_points": ["resource behavior"], "release_note": "resource accessor contract", "open_questions": []},
                    "non_goals": ["No synthetic payload argument."],
                },
            }
        }
    )

    assert "spec_writer.io_contract_shapes_specific" not in quality["warnings"]


def test_foundation_semantic_quality_normalizes_adr_location_suffix_for_spec_candidate() -> None:
    quality = evaluate_foundation_semantic_quality(
        {
            "artifacts": {
                "project_map_report": {
                    "summary": {"root": "demo", "frameworks": [], "entrypoints": ["pkg.py"]},
                    "answers": {
                        "1_scope": {
                            "main_task": "Provide package response sender behavior for integration consumers.",
                            "supported_scenarios": ["send response", "handle failure"],
                            "inputs": ["event"],
                            "outputs": ["delivery result"],
                            "domain_profile": {"kind": "integration_sender", "confidence": 0.7, "evidence": ["pkg.py:send"]},
                        },
                        "2_execution": {"primary_execution_path": ["pkg.py:send"]},
                        "3_capabilities": {"atomic_reusable_capabilities": ["pkg.py:send"]},
                        "4_contracts_data": {"main_data_structures": ["Event"], "weak_contract_zones": []},
                        "5_errors_state_repro": {
                            "likely_error_types": ["transport error"],
                            "state_to_preserve": ["request id"],
                            "minimal_cognitive_loop": ["build", "send", "report"],
                        },
                        "6_runtime_extraction_readiness": {
                            "data_lifecycle": [{"stage": "input"}, {"stage": "send"}, {"stage": "output"}],
                            "minimal_extraction_plan": {"capabilities_to_extract": [{"capability": "pkg.py:send", "reason": "bounded sender"}]},
                            "evidence_claims": [{"source": "pkg.py:send"}, {"source": "pkg.py:build"}, {"source": "pkg.py:error"}],
                        },
                    },
                },
                "architecture_decision": {
                    "decision_summary": "Select the response sender as the first bounded integration slice.",
                    "architecture_synthesis": {"project_profile": {"archetype": "integration_sender", "domain_profile_kind": "integration_sender"}},
                    "first_slice_contract": {"targets": ["pkg.py:send(40 loc)"]},
                    "architecture_options": [{"id": "extract_sender"}, {"id": "full_rewrite"}],
                    "rejected_options": [{"id": "full_rewrite"}],
                    "spec_writer_brief": {
                        "files_or_symbols": ["pkg.py:send(40 loc)"],
                        "contract_targets": ["pkg.py:send(40 loc)"],
                        "acceptance_targets": ["transport failure is typed"],
                    },
                    "risks": [{"risk": "Transport failures can be hidden.", "mitigation": "Contract tests cover typed failure packets."}],
                    "fact_judgment_ledger": {
                        "facts": [{"claim": "pkg.py:send exists"}],
                        "judgments": [{"judgment": "sender is bounded", "validation_gate": "fake transport tests"}],
                    },
                    "source_context": {"pkg.py:send": {}, "pkg.py:build": {}, "pkg.py:error": {}},
                    "open_questions": [],
                    "non_goals": ["Do not call live transport in unit tests."],
                },
                "technical_spec": {
                    "extraction_contract": {
                        "candidate": "pkg.py:send",
                        "ranked_candidates": [{"source": "pkg.py:send"}],
                        "contract_family": "integration_send_boundary",
                        "input_contract": {"event": "IntegrationEvent"},
                        "output_contract": {"result": "DeliveryResult"},
                        "side_effects": {"declared": [], "external_calls": "fake transport"},
                    },
                    "requirements": [
                        {"statement": "Build the response body from event fields."},
                        {"statement": "Send through a fakeable transport boundary."},
                        {"statement": "Return typed delivery failures for transport errors."},
                    ],
                    "acceptance_criteria": [
                        {"criterion": "Successful response send returns delivery result.", "verification": "Run fake transport contract test."},
                        {"criterion": "Transport error returns typed failure.", "verification": "Run negative fake transport test."},
                        {"criterion": "Malformed event is rejected.", "verification": "Run malformed event fixture."},
                    ],
                    "traceability_table": [
                        {"source": "pkg.py:send", "acceptance_id": "AC-001"},
                        {"source": "pkg.py:send", "acceptance_id": "AC-002"},
                        {"source": "pkg.py:send", "acceptance_id": "AC-003"},
                    ],
                    "work_plan_contract": {"obligations": ["preserve response sender contract"]},
                    "implementation_handoff": {"patch_scope": ["pkg.py:send"]},
                    "human_review": {"decision_points": ["response sender"], "release_note": "sender contract", "open_questions": []},
                    "non_goals": ["No live transport in unit tests."],
                },
            }
        }
    )

    assert "spec_writer.candidate_backed_by_adr" not in quality["warnings"]


def test_foundation_semantic_quality_allows_generic_slice_with_profiled_target() -> None:
    quality = evaluate_foundation_semantic_quality(
        {
            "artifacts": {
                "project_map_report": {
                    "summary": {"root": "airflow", "frameworks": ["pluggy"], "entrypoints": ["src/airflow/__main__.py:main"]},
                    "answers": {
                        "1_scope": {
                            "main_task": "Load workflow platform settings and register plugins through policy hooks.",
                            "supported_scenarios": ["load local settings", "register plugin hooks"],
                            "inputs": ["settings module", "plugin manager"],
                            "outputs": ["plugin registration state"],
                            "domain_profile": {"kind": "workflow_orchestrator", "confidence": 0.8, "evidence": ["plugin", "settings"]},
                        },
                        "2_execution": {"primary_execution_path": ["src/airflow/policies.py:make_plugin_from_local_settings"]},
                        "3_capabilities": {"atomic_reusable_capabilities": ["src/airflow/policies.py:make_plugin_from_local_settings"]},
                        "4_contracts_data": {"main_data_structures": ["PluginManager"], "weak_contract_zones": []},
                        "5_errors_state_repro": {
                            "likely_error_types": ["settings import error"],
                            "state_to_preserve": ["plugin registry state"],
                            "minimal_cognitive_loop": ["load", "register", "report"],
                        },
                        "6_runtime_extraction_readiness": {
                            "data_lifecycle": [{"stage": "settings"}, {"stage": "registration"}, {"stage": "result"}],
                            "minimal_extraction_plan": {
                                "capabilities_to_extract": [
                                    {
                                        "capability": "src/airflow/policies.py:make_plugin_from_local_settings",
                                        "reason": "plugin settings registration is bounded",
                                    }
                                ]
                            },
                            "evidence_claims": [{"source": "src/airflow/policies.py:make_plugin_from_local_settings"}] * 3,
                        },
                    },
                },
                "architecture_decision": {
                    "decision_summary": "Select plugin settings registration as the first source-backed contract.",
                    "architecture_synthesis": {
                        "project_profile": {"archetype": "workflow_orchestrator", "domain_profile_kind": "workflow_orchestrator"}
                    },
                    "first_slice_contract": {
                        "name": "workflow_state_transition_slice",
                        "targets": ["src/airflow/policies.py:make_plugin_from_local_settings"],
                    },
                    "architecture_options": [{"id": "plugin_settings"}, {"id": "scheduler_rewrite"}],
                    "rejected_options": [{"id": "scheduler_rewrite"}],
                    "spec_writer_brief": {
                        "files_or_symbols": ["src/airflow/policies.py:make_plugin_from_local_settings"],
                        "contract_targets": ["src/airflow/policies.py:make_plugin_from_local_settings"],
                        "acceptance_targets": ["duplicate plugin registration is typed"],
                    },
                    "risks": [{"risk": "Plugin registry mutation can drift.", "mitigation": "Snapshot before/after state."}],
                    "fact_judgment_ledger": {
                        "facts": [{"claim": "plugin settings target exists"}],
                        "judgments": [{"judgment": "target is profiled semantic contract", "validation_gate": "contract tests"}],
                    },
                    "source_context": {
                        "src/airflow/policies.py:make_plugin_from_local_settings": {},
                        "src/airflow/providers_manager.py": {},
                        "src/airflow/settings.py": {},
                    },
                    "open_questions": [],
                    "non_goals": ["Do not alter scheduler execution."],
                },
                "technical_spec": {},
            }
        }
    )

    assert "architect.first_slice_not_generic_when_domain_cues_exist" not in quality["warnings"]
