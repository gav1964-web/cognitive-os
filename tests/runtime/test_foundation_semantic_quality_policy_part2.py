from __future__ import annotations

from runtime.foundation_semantic_quality import evaluate_foundation_semantic_quality


def test_foundation_semantic_quality_allows_generic_slice_with_profiled_target() -> None:
    target = "src/airflow/policies.py:make_plugin_from_local_settings"
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
                        "2_execution": {"primary_execution_path": [target]},
                        "3_capabilities": {"atomic_reusable_capabilities": [target]},
                        "4_contracts_data": {"main_data_structures": ["PluginManager"], "weak_contract_zones": []},
                        "5_errors_state_repro": {
                            "likely_error_types": ["settings import error"],
                            "state_to_preserve": ["plugin registry state"],
                            "minimal_cognitive_loop": ["load", "register", "report"],
                        },
                        "6_runtime_extraction_readiness": {
                            "data_lifecycle": [{"stage": "settings"}, {"stage": "registration"}, {"stage": "result"}],
                            "minimal_extraction_plan": {
                                "capabilities_to_extract": [{"capability": target, "reason": "plugin settings registration is bounded"}]
                            },
                            "evidence_claims": [{"source": target}] * 3,
                        },
                    },
                },
                "architecture_decision": {
                    "decision_summary": "Select plugin settings registration as the first source-backed contract.",
                    "architecture_synthesis": {
                        "project_profile": {"archetype": "workflow_orchestrator", "domain_profile_kind": "workflow_orchestrator"}
                    },
                    "first_slice_contract": {"name": "workflow_state_transition_slice", "targets": [target]},
                    "architecture_options": [{"id": "plugin_settings"}, {"id": "scheduler_rewrite"}],
                    "rejected_options": [{"id": "scheduler_rewrite"}],
                    "spec_writer_brief": {
                        "files_or_symbols": [target],
                        "contract_targets": [target],
                        "acceptance_targets": ["duplicate plugin registration is typed"],
                    },
                    "risks": [{"risk": "Plugin registry mutation can drift.", "mitigation": "Snapshot before/after state."}],
                    "fact_judgment_ledger": {
                        "facts": [{"claim": "plugin settings target exists"}],
                        "judgments": [{"judgment": "target is profiled semantic contract", "validation_gate": "contract tests"}],
                    },
                    "source_context": {target: {}, "src/airflow/providers_manager.py": {}, "src/airflow/settings.py": {}},
                    "open_questions": [],
                    "non_goals": ["Do not alter scheduler execution."],
                },
                "technical_spec": {},
            }
        }
    )

    assert "architect.first_slice_not_generic_when_domain_cues_exist" not in quality["warnings"]


def test_profiled_target_still_requires_domain_named_first_slice() -> None:
    target = "src/codec/msgpack.py:decode_message"
    payload = {
        "artifacts": {
            "project_map_report": {
                "summary": {"root": "codec", "frameworks": [], "entrypoints": ["src/codec/__main__.py:main"]},
                "answers": {
                    "1_scope": {
                        "main_task": "Decode msgpack payloads into typed message objects for downstream consumers.",
                        "supported_scenarios": ["decode payload", "reject malformed payload"],
                        "inputs": ["binary msgpack payload"],
                        "outputs": ["typed message object"],
                        "domain_profile": {"kind": "binary_codec", "confidence": 0.8, "evidence": ["msgpack", "codec"]},
                    },
                    "2_execution": {"primary_execution_path": [target]},
                    "3_capabilities": {"atomic_reusable_capabilities": [target]},
                    "4_contracts_data": {"main_data_structures": ["Message"], "weak_contract_zones": []},
                    "5_errors_state_repro": {
                        "likely_error_types": ["malformed payload"],
                        "state_to_preserve": ["offset", "schema"],
                        "minimal_cognitive_loop": ["read", "decode", "validate"],
                    },
                    "6_runtime_extraction_readiness": {
                        "data_lifecycle": [{"stage": "read"}, {"stage": "decode"}, {"stage": "validate"}],
                        "minimal_extraction_plan": {"capabilities_to_extract": [{"capability": target, "reason": "bounded codec transform"}]},
                        "evidence_claims": [{"source": target}] * 3,
                    },
                },
            },
            "architecture_decision": {
                "decision_summary": "Select binary payload decoding as the first source-backed contract.",
                "architecture_synthesis": {"project_profile": {"archetype": "library", "domain_profile_kind": "binary_codec"}},
                "first_slice_contract": {"name": "configuration_parse_lookup_slice", "targets": [target]},
                "architecture_options": [{"id": "codec_decode"}, {"id": "schema_rewrite"}],
                "rejected_options": [{"id": "schema_rewrite"}],
                "spec_writer_brief": {"files_or_symbols": [target], "contract_targets": [target], "acceptance_targets": ["malformed payload rejected"]},
                "risks": [{"risk": "Malformed frames can leak parser errors.", "mitigation": "Normalize decode failures."}],
                "fact_judgment_ledger": {
                    "facts": [{"claim": "decode target exists"}],
                    "judgments": [{"judgment": "decode target is bounded", "validation_gate": "fixture tests"}],
                },
                "source_context": {target: {}, "src/codec/types.py": {}, "src/codec/errors.py": {}},
                "open_questions": [],
                "non_goals": ["Do not change message schema."],
            },
            "technical_spec": {},
        }
    }

    quality = evaluate_foundation_semantic_quality(payload)

    assert "architect.first_slice_not_generic_when_domain_cues_exist" in quality["warnings"]
