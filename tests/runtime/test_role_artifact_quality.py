from __future__ import annotations

from pathlib import Path

from runtime.project_benchmark import analyze_project
from runtime.role_artifact_interpreter import run_role_artifact_pipeline
from runtime.role_artifact_quality import (
    evaluate_architecture_decision,
    evaluate_role_artifacts,
    evaluate_technical_spec,
)


ROOT = Path(__file__).resolve().parents[2]


def test_role_artifact_quality_passes_foundation_artifacts():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_role_artifact_pipeline(goal="Extract first safe capability", project_report=project_report)

    quality = evaluate_role_artifacts(artifacts)

    assert quality["passed"] is True
    assert quality["score"] == 1.0
    assert quality["warnings"] == []
    assert set(quality["results"]) == {
        "adr",
        "technical_spec",
        "implementation_plan",
        "test_plan",
        "review_findings",
    }


def test_role_artifact_quality_rejects_generic_artifacts():
    quality = evaluate_role_artifacts(
        {
            "architecture_decision": {
                "decision_summary": "Improve architecture.",
                "chosen_option": {"reason": "best practices"},
                "capability_model": [{"source": "thing"}],
                "risks": [{"description": "clean up"}],
                "traceability": [],
                "spec_writer_brief": {},
            },
            "technical_spec": {
                "requirements": [{"statement": "refactor as needed", "priority": "MUST"}],
                "acceptance_criteria": [{"criterion": "make it better", "verification": "review"}],
                "extraction_contract": {},
                "source_evidence": [],
                "traceability_table": [],
                "implementation_handoff": {},
            },
        }
    )

    assert quality["passed"] is False
    assert quality["score"] < 0.9
    assert "adr.avoids_generic_phrases" in quality["warnings"]
    assert "technical_spec.avoids_generic_phrases" in quality["warnings"]


def test_role_artifact_quality_rejects_unbacked_first_slice_and_ranking():
    adr = {
        "decision_summary": "Extract a focused capability from the current project report.",
        "chosen_option": {"reason": "highest fit-to-risk score for bounded extraction"},
        "architecture_options": [
            {"id": "a", "tradeoffs": ["small scope"]},
            {"id": "b", "tradeoffs": ["broader cleanup"]},
        ],
        "subsystem_boundaries": [
            {
                "owned_files": ["main.py"],
                "inputs": ["request"],
                "outputs": ["response"],
            }
        ],
        "data_lifecycle": [{"stage": "input"}],
        "state_model": [{"owner": "execution_inputs"}],
        "capability_model": [{"source": "main.py:do_work"}],
        "risks": [{"risk": "contract drift", "mitigation": "add contract tests"}],
        "traceability": [{"source": "analysis_task", "target": "main.py:do_work"}],
        "spec_writer_brief": {
            "files_or_symbols": ["main.py:do_work"],
            "contract_targets": [{"source": "main.py:do_work"}],
        },
        "first_slice_contract": {
            "name": "first_slice",
            "targets": ["main.py:do_work"],
        },
        "architecture_synthesis": {
            "project_profile": {"archetype": "generic"},
        },
        "source_context": {},
    }
    spec = {
        "requirements": [{"statement": "Extract main.py:do_work as a bounded capability."}],
        "acceptance_criteria": [{"criterion": "contract test passes", "verification": "pytest"}],
        "interface_contracts": [{"source": "main.py:do_work", "input_contract": {"x": "str"}, "output_contract": {"result": "str"}}],
        "work_plan_contract": {"goal": "extract do_work", "obligations": [{"id": "o1", "step": "preserve IO"}]},
        "data_lifecycle": [{"stage": "input"}],
        "error_model": [{"handling": "fail closed on invalid input"}],
        "extraction_contract": {
            "candidate": "main.py:do_work",
            "ranked_candidates": [{"source": "main.py:other_work"}],
            "input_contract": {"x": "str"},
            "output_contract": {"result": "str"},
            "semantic_quality": {"status": "poor"},
        },
        "source_evidence": [],
        "traceability_table": [{"source": "main.py:do_work", "acceptance_id": "AC-1"}],
        "implementation_handoff": {"recommended_role": "implementer", "patch_scope": ["main.py"]},
    }

    adr_quality = evaluate_architecture_decision(adr)
    spec_quality = evaluate_technical_spec(spec)

    assert "first_slice_has_evidence_density" in adr_quality["warnings"]
    assert "architecture_synthesis_is_project_specific" in adr_quality["warnings"]
    assert "ranked_candidates_have_selection_reasons" in spec_quality["warnings"]
    assert "selected_candidate_quality_is_usable" in spec_quality["warnings"]
    assert "selected_candidate_is_source_backed" in spec_quality["warnings"]


def test_project_map_quality_rejects_scope_domain_profile_conflict():
    quality = evaluate_role_artifacts(
        {
            "project_map_report": {
                "summary": {"root": "demo", "file_count": 3},
                "answers": {
                    "1_scope": {
                        "main_task": "Provide a unified OpenAI-compatible gateway for routing chat requests.",
                        "inputs": ["prompt cases"],
                        "outputs": ["analysis reports"],
                        "code_areas": {"core_logic": ["prompt_lab.py"]},
                        "domain_profile": {
                            "kind": "prompt_lab_evaluation_runtime",
                            "purpose_summary": "Run a prompt laboratory for repeatable prompt validation and enrichment experiments.",
                        },
                    },
                    "2_execution": {"entrypoints": ["prompt_lab.py"], "primary_execution_path": ["run prompt lab"]},
                    "3_capabilities": {"atomic_reusable_capabilities": ["prompt_lab.py:run_auto_loop_once"]},
                    "4_contracts_data": {"main_data_structures": ["PromptCase"], "weak_contract_zones": []},
                    "5_errors_state_repro": {
                        "likely_error_types": ["bad input"],
                        "state_to_preserve": ["run artifacts"],
                        "minimal_cognitive_loop": ["run", "analyze"],
                    },
                    "6_runtime_extraction_readiness": {
                        "data_lifecycle": [{"stage": "input"}],
                        "minimal_extraction_plan": {"capabilities_to_extract": [{"capability": "prompt_lab.py:run_auto_loop_once"}]},
                    },
                },
            },
            "architecture_decision": {},
            "technical_spec": {},
        }
    )

    assert "project_map_report.scope_matches_domain_profile" in quality["warnings"]
