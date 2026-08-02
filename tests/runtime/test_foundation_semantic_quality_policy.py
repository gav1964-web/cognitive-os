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
