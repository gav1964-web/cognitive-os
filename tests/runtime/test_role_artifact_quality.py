from __future__ import annotations

from pathlib import Path

from runtime.project_benchmark import analyze_project
from runtime.foundation_semantic_quality import evaluate_foundation_semantic_quality
from runtime.role_artifact_interpreter import run_role_artifact_pipeline
from runtime.role_foundation_pipeline import score_role_foundation
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


def test_role_artifact_quality_ignores_generic_phrases_inside_source_snippets():
    adr = {
        "decision_summary": "Extract a focused parser boundary from source-backed evidence.",
        "chosen_option": {"reason": "bounded source-backed parser target has the smallest safe scope"},
        "architecture_options": [
            {"id": "parser", "tradeoffs": ["small deterministic target"]},
            {"id": "workflow", "tradeoffs": ["broader side-effect boundary"]},
        ],
        "subsystem_boundaries": [{"owned_files": ["pkg/parser.py"], "inputs": ["raw text"], "outputs": ["parsed document"]}],
        "data_lifecycle": [{"stage": "input"}],
        "state_model": [{"owner": "input payload"}],
        "capability_model": [{"source": "pkg/parser.py:parse_document"}],
        "risks": [{"description": "Parser drift can break malformed input handling.", "mitigation": "Add negative fixture tests."}],
        "traceability": [{"source": "ProjectArchitectureSynthesis.recommended_first_slice", "target": "pkg/parser.py:parse_document"}],
        "spec_writer_brief": {
            "files_or_symbols": ["pkg/parser.py:parse_document"],
            "contract_targets": [{"source": "pkg/parser.py:parse_document"}],
            "acceptance_targets": ["Malformed input returns a typed failure packet."],
            "constraints": ["no source rewrite in architecture phase"],
        },
        "first_slice_contract": {"name": "parser_slice", "targets": ["pkg/parser.py:parse_document"]},
        "architecture_synthesis": {"project_profile": {"archetype": "document_parser"}},
        "source_context": {
            "pkg/parser.py:parse_document": {
                "snippet": {"text": "def parse_document(raw):\n    # clean up legacy comments from input\n    return raw"}
            }
        },
        "fact_judgment_ledger": {
            "facts": [{"claim": "Parser target exists.", "source": "pkg/parser.py:parse_document"}],
            "judgments": [{"judgment": "Parser is bounded.", "validation_gate": "contract tests"}],
        },
        "handoff_readiness": {"gates": ["spec_writer_red_team"]},
    }
    spec = {
        "requirements": [{"statement": "Extract pkg/parser.py:parse_document as the first parser capability.", "priority": "MUST"}],
        "acceptance_criteria": [
            {"criterion": "Malformed parser input returns a typed failure packet.", "verification": "Run parser negative tests."}
        ],
        "interface_contracts": [{"source": "pkg/parser.py:parse_document", "input_contract": {"raw": "RawText"}, "output_contract": {"result": "ParsedDocument"}}],
        "work_plan_contract": {"name": "parser_slice", "obligations": [{"id": "WPC-001", "step": "Preserve parser input/output shape."}]},
        "data_lifecycle": [{"stage": "input"}],
        "error_model": [{"handling": "Return typed parser failure for invalid input."}],
        "extraction_contract": {
            "candidate": "pkg/parser.py:parse_document",
            "ranked_candidates": [{"source": "pkg/parser.py:parse_document", "reasons": ["source-backed parser target"]}],
            "input_contract": {"raw": "RawText"},
            "output_contract": {"result": "ParsedDocument"},
            "side_effects": {"declared": []},
            "semantic_quality": {"status": "strong", "score": 90},
        },
        "source_evidence": [
            {
                "source": "pkg/parser.py:parse_document",
                "snippet": "def parse_document(raw):\n    # clean up legacy comments from input\n    return raw",
            }
        ],
        "traceability_table": [{"source": "pkg/parser.py:parse_document", "acceptance_id": "AC-001"}],
        "implementation_handoff": {"recommended_role": "implementer", "patch_scope": ["pkg/parser.py:parse_document"]},
        "engineering_quality_gate": {"status": "ready"},
        "open_questions": [],
        "non_goals": ["Do not rewrite unrelated parser modules."],
    }

    quality = evaluate_role_artifacts({"architecture_decision": adr, "technical_spec": spec})

    assert "adr.avoids_generic_phrases" not in quality["warnings"]
    assert "technical_spec.avoids_generic_phrases" not in quality["warnings"]


def test_role_artifact_quality_keeps_generic_phrase_as_advisory_when_score_is_high():
    checks = {f"check_{index}": True for index in range(12)}
    checks["avoids_generic_phrases"] = False

    from runtime.role_artifact_quality import _result

    result = _result(checks)

    assert result["score"] > 0.9
    assert result["passed"] is True
    assert result["warnings"] == ["avoids_generic_phrases"]
    assert result["blocking_warnings"] == []


def test_technical_spec_allows_empty_input_contract_for_zero_arg_target():
    spec = {
        "requirements": [{"statement": "Bind pkg/core.py:contents as a zero-argument capability.", "priority": "MUST"}],
        "acceptance_criteria": [
            {"criterion": "Calling pkg/core.py:contents returns the configured payload.", "verification": "Run callable acceptance."}
        ],
        "interface_contracts": [{"source": "pkg/core.py:contents", "input_contract": {}, "output_contract": {"result": "Text"}}],
        "work_plan_contract": {
            "goal": "Bind pkg/core.py:contents as a zero-argument capability.",
            "obligations": [{"id": "WPC-001", "step": "Preserve the zero-argument callable contract."}],
        },
        "data_lifecycle": [{"stage": "call", "owner": "pkg/core.py:contents"}],
        "error_model": [{"handling": "Surface import or resource errors as controlled test failures."}],
        "extraction_contract": {
            "candidate": "pkg/core.py:contents",
            "ranked_candidates": [{"source": "pkg/core.py:contents", "reasons": ["source-backed zero-argument target"]}],
            "input_contract": {},
            "output_contract": {"result": "Text"},
            "side_effects": {"declared": []},
            "semantic_quality": {"status": "strong", "score": 90},
        },
        "source_evidence": [{"source": "pkg/core.py:contents", "snippet": "def contents():\n    return where.read_text()"}],
        "traceability_table": [{"source": "pkg/core.py:contents", "acceptance_id": "AC-001"}],
        "implementation_handoff": {"recommended_role": "implementer", "patch_scope": ["pkg/core.py:contents"]},
        "engineering_quality_gate": {
            "status": "ready",
            "checks": {
                "source_evidence_bound": True,
                "io_contract_bound": True,
                "negative_acceptance_present": True,
                "handoff_scope_bound": True,
            },
        },
        "open_questions": [],
        "non_goals": ["Do not invent synthetic payload arguments for zero-argument callables."],
    }

    quality = evaluate_technical_spec(spec)

    assert quality["checks"]["interface_contracts_present"] is True
    assert quality["checks"]["contract_has_io"] is True
    assert quality["passed"] is True


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


def test_foundation_semantic_quality_rejects_shallow_foundation_artifacts():
    report = {
        "artifacts": {
            "project_map_report": {
                "summary": {"root": "demo", "file_count": 10, "frameworks": ["FastAPI"], "entrypoints": ["app.py"]},
                "answers": {
                    "1_scope": {
                        "main_task": "Run project workflows.",
                        "supported_scenarios": ["run"],
                        "inputs": ["input"],
                        "outputs": ["output"],
                        "domain_profile": {"kind": "generic", "confidence": 0.0, "evidence": []},
                    },
                    "2_execution": {},
                    "3_capabilities": {},
                    "4_contracts_data": {"main_data_structures": [], "weak_contract_zones": []},
                    "5_errors_state_repro": {},
                    "6_runtime_extraction_readiness": {"data_lifecycle": [], "minimal_extraction_plan": {}},
                },
            },
            "architecture_decision": {
                "decision_summary": "Improve architecture.",
                "architecture_synthesis": {"project_profile": {"archetype": "generic"}},
                "architecture_options": [],
                "first_slice_contract": {},
                "spec_writer_brief": {},
                "risks": [],
                "traceability": [],
                "source_context": {},
            },
            "technical_spec": {
                "extraction_contract": {"candidate": "", "input_contract": {}, "output_contract": {}},
                "requirements": [],
                "acceptance_criteria": [],
            },
        }
    }

    quality = evaluate_foundation_semantic_quality(report)

    assert quality["status"] == "needs_work"
    assert quality["role_scores"]["project_analyzer"] < 8.8
    assert "project_analyzer.domain_profile_is_specific_or_evidently_generic" in quality["warnings"]
    assert "architect.options_and_rejections_have_tradeoffs" in quality["warnings"]
    assert "spec_writer.negative_or_edge_cases_present" in quality["warnings"]


def test_role_foundation_score_uses_semantic_quality_not_only_field_presence():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    project_report = analyze_project(project_dir)["project_map_report"]
    project_report["answers"]["1_scope"]["main_task"] = (
        "Trusted by major teams since 2020; includes badges and downloads, "
        "while actual module parser and protocol behavior is only implied."
    )
    project_report["answers"]["1_scope"]["domain_profile"] = {
        "kind": "generic",
        "confidence": 0.0,
        "evidence": [],
    }
    artifacts = run_role_artifact_pipeline(goal="Extract first safe capability", project_report=project_report)
    artifacts["project_map_report"] = {"artifact_type": "ProjectMapReport", "content": project_report}

    score = score_role_foundation(artifacts)

    assert score["passed"] is False
    assert score["semantic_score"] < score["artifact_score"]
    assert score["overall_score"] == score["semantic_score"]
    assert score["min_role_score_10pt"] < 8.8
    assert "foundation_semantic_quality_passed" in score["warnings"]
    assert "project_analyzer.purpose_avoids_marketing_blurb" in score["foundation_semantic_quality"]["warnings"]
    assert "project_analyzer.generic_profile_not_masking_library_domain" in score["foundation_semantic_quality"]["warnings"]
