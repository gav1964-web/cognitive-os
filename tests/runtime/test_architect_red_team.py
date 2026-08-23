from __future__ import annotations

from runtime.architect_red_team import _looks_like_contract_type_ref, red_team_architecture_decision


def test_class_qualified_method_is_not_misclassified_as_contract_type():
    assert not _looks_like_contract_type_ref("store.py:Store.set_value")
    assert _looks_like_contract_type_ref("store.py:Store.UpdateResult")


def test_architect_red_team_accepts_bounded_source_backed_adr():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "project": "demo",
        "chosen_option": {"id": "minimal_safe_extraction", "reason": "bounded first transformation"},
        "architecture_options": [
            {"id": "minimal_safe_extraction", "tradeoffs": ["small blast radius"]},
            {"id": "contract_hardening_first", "tradeoffs": ["slower but safer"]},
        ],
        "rejected_options": [
            {
                "id": "contract_hardening_first",
                "reason_rejected": "lower score for the first slice",
                "tradeoffs": ["slower but safer"],
                "deferred_until": "after first slice fails",
                "score_delta": 2,
            }
        ],
        "first_slice_contract": {
            "name": "parser_slice",
            "goal": "Extract parser boundary.",
            "targets": ["parser.py:parse"],
            "steps": ["Define ParserInput.", "Define ParserOutput."],
            "selection_policy": "smallest source-backed slice",
            "handoff_expectation": "SpecWriter may rerank weak targets",
        },
        "spec_writer_brief": {
            "files_or_symbols": ["parser.py:parse"],
            "acceptance_targets": ["parser.py:parse has contract tests."],
            "constraints": ["no source rewrite in architecture phase"],
            "contract_targets": [{"source": "parser.py:parse"}],
        },
        "source_context": {"parser.py:parse": {"signature": {"args": [], "returns": "dict"}}},
        "traceability": [{"source": "parser.py:parse", "target": "parser.py:parse"}],
        "risks": [
            {
                "severity": "medium",
                "description": "Parser input may be malformed.",
                "impact": "Bad input can break contract verification.",
                "mitigation": "Add negative tests.",
                "evidence_source": "parser.py:parse",
            }
        ],
        "open_questions": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

    report = red_team_architecture_decision(adr, {"project": "demo"})

    assert report["status"] == "pass"
    assert report["handoff_verdict"] == "ready_for_spec_writer"


def test_architect_red_team_normalizes_loc_suffix_in_brief_sources():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "project": "demo",
        "chosen_option": {"id": "minimal_safe_extraction", "reason": "bounded first transformation"},
        "architecture_options": [
            {"id": "minimal_safe_extraction", "tradeoffs": ["small blast radius"]},
            {"id": "contract_hardening_first", "tradeoffs": ["slower but safer"]},
        ],
        "rejected_options": [
            {
                "id": "contract_hardening_first",
                "reason_rejected": "first slice is smaller",
                "tradeoffs": ["slower but safer"],
                "deferred_until": "after first slice",
                "score_delta": 1,
            }
        ],
        "first_slice_contract": {
            "name": "provider_slice",
            "goal": "Extract provider listing boundary.",
            "targets": ["api.py:list_provider_capabilities(2 loc)"],
            "steps": ["Define ProviderListRequest.", "Define ProviderListResponse."],
            "selection_policy": "smallest source-backed slice",
            "handoff_expectation": "SpecWriter may normalize source refs",
        },
        "spec_writer_brief": {
            "files_or_symbols": ["api.py:list_provider_capabilities(2 loc)"],
            "acceptance_targets": ["api.py:list_provider_capabilities has contract tests."],
            "constraints": ["no source rewrite in architecture phase"],
            "contract_targets": [{"source": "api.py:list_provider_capabilities(2 loc)"}],
        },
        "source_context": {"api.py:list_provider_capabilities": {"signature": {"args": [], "returns": "dict"}}},
        "traceability": [{"source": "api.py:list_provider_capabilities", "target": "api.py:list_provider_capabilities"}],
        "risks": [
            {
                "severity": "medium",
                "description": "Provider list may drift.",
                "impact": "Bad provider metadata can confuse callers.",
                "mitigation": "Add contract tests.",
                "evidence_source": "api.py:list_provider_capabilities",
            }
        ],
        "open_questions": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

    report = red_team_architecture_decision(adr, {"project": "demo"})

    assert "brief_sources_without_context" not in {row["code"] for row in report["warnings"]}


def test_architect_red_team_does_not_require_source_context_for_contract_type_refs():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "project": "demo",
        "chosen_option": {"id": "minimal_safe_extraction", "reason": "bounded runtime detection"},
        "architecture_options": [
            {"id": "minimal_safe_extraction", "tradeoffs": ["small blast radius"]},
            {"id": "contract_hardening_first", "tradeoffs": ["slower but safer"]},
        ],
        "rejected_options": [
            {
                "id": "contract_hardening_first",
                "reason_rejected": "first slice already has source-backed executable target",
                "tradeoffs": ["slower but safer"],
                "deferred_until": "after first slice",
                "score_delta": 1,
            }
        ],
        "first_slice_contract": {
            "name": "async_context_detection_slice",
            "goal": "Detect active async runtime context.",
            "targets": ["runtime.py:current_async_library"],
            "steps": ["Define RuntimeContext.", "Define AsyncContextDetectionFailure."],
            "selection_policy": "smallest source-backed slice",
            "handoff_expectation": "SpecWriter may use contract type refs as supporting types",
        },
        "spec_writer_brief": {
            "files_or_symbols": [
                "runtime.py:current_async_library",
                "runtime.py:AsyncLibraryNotFoundError",
                "runtime.py:current_async_library(71 loc)",
            ],
            "acceptance_targets": ["runtime.py:current_async_library has contract tests."],
            "constraints": ["no source rewrite in architecture phase"],
            "contract_targets": [{"source": "runtime.py:current_async_library"}],
        },
        "source_context": {"runtime.py:current_async_library": {"signature": {"args": [], "returns": "str"}}},
        "traceability": [{"source": "runtime.py:current_async_library", "target": "runtime.py:current_async_library"}],
        "risks": [
            {
                "severity": "medium",
                "description": "Runtime detection can fail outside async context.",
                "impact": "Caller gets ambiguous runtime behavior.",
                "mitigation": "Add negative tests for sync context.",
                "evidence_source": "runtime.py:current_async_library",
            }
        ],
        "open_questions": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

    report = red_team_architecture_decision(adr, {"project": "demo"})

    assert "brief_sources_without_context" not in {row["code"] for row in report["warnings"]}


def test_architect_red_team_blocks_unbounded_adr():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "architecture_options": [{"id": "minimal_safe_extraction"}],
        "rejected_options": [],
        "first_slice_contract": {"name": "slice", "targets": ["maybe"], "steps": []},
        "spec_writer_brief": {"files_or_symbols": ["maybe"]},
        "source_context": {},
        "traceability": [],
        "risks": [{"severity": "medium", "description": "Something is risky."}],
        "forbidden_actions_enforced": [],
    }

    report = red_team_architecture_decision(adr)

    assert report["status"] == "fail"
    assert report["handoff_verdict"] == "return_to_architect"
    codes = {row["code"] for row in report["blocking_findings"]}
    assert "missing_option_tradeoffs" in codes
    assert "first_slice_not_bounded" in codes
    assert "risks_not_actionable" in codes


def test_architect_red_team_blocks_noisy_source_tree_without_scope_decision():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "project": "demo",
        "chosen_option": {"id": "minimal_safe_extraction", "reason": "bounded first transformation"},
        "architecture_options": [
            {"id": "minimal_safe_extraction", "tradeoffs": ["small blast radius"]},
            {"id": "contract_hardening_first", "tradeoffs": ["slower but safer"]},
        ],
        "rejected_options": [
            {
                "id": "contract_hardening_first",
                "reason_rejected": "lower score for the first slice",
                "tradeoffs": ["slower but safer"],
                "deferred_until": "after root scope is clean",
                "score_delta": 2,
            }
        ],
        "first_slice_contract": {
            "name": "agent_consensus_orchestration_slice",
            "goal": "Extract orchestration boundary.",
            "targets": ["core/consensus/engine.py:run_consensus"],
            "steps": ["Define ConsensusInput.", "Define ConsensusResult."],
            "selection_policy": "smallest source-backed slice",
            "handoff_expectation": "SpecWriter may rerank weak targets",
        },
        "spec_writer_brief": {
            "files_or_symbols": ["core/consensus/engine.py:run_consensus"],
            "acceptance_targets": ["consensus has contract tests."],
            "constraints": ["no source rewrite in architecture phase"],
            "contract_targets": [{"source": "core/consensus/engine.py:run_consensus"}],
        },
        "source_context": {"core/consensus/engine.py:run_consensus": {"signature": {"args": [], "returns": "dict"}}},
        "traceability": [{"source": "core/consensus/engine.py:run_consensus", "target": "core/consensus/engine.py:run_consensus"}],
        "risks": [
            {
                "severity": "medium",
                "description": "Consensus failure needs a contract.",
                "impact": "Bad agent response can break execution.",
                "mitigation": "Add negative tests.",
                "evidence_source": "core/consensus/engine.py:run_consensus",
            }
        ],
        "open_questions": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

    report = red_team_architecture_decision(
        adr,
        {
            "content": {
                "source_health": {
                    "status": "noisy",
                    "project_shape": "dirty_portfolio",
                    "packaged_copy_signal_count": 4,
                }
            }
        },
    )

    assert report["status"] == "fail"
    codes = {row["code"] for row in report["blocking_findings"]}
    assert "source_tree_requires_scope_decision" in codes


def test_architect_red_team_allows_fixture_only_syntax_damage():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "project": "demo",
        "chosen_option": {"id": "minimal_safe_extraction", "reason": "bounded first transformation"},
        "architecture_options": [
            {"id": "minimal_safe_extraction", "tradeoffs": ["small blast radius"]},
            {"id": "contract_hardening_first", "tradeoffs": ["slower but safer"]},
        ],
        "rejected_options": [
            {
                "id": "contract_hardening_first",
                "reason_rejected": "first slice is ready",
                "tradeoffs": ["slower but safer"],
                "deferred_until": "after first slice",
                "score_delta": 1,
            }
        ],
        "first_slice_contract": {
            "name": "diff_parser_slice",
            "goal": "Parse unified diff input.",
            "targets": ["pycodestyle.py:parse_udiff"],
            "steps": ["Define UDiffInput.", "Define ParsedDiff."],
            "selection_policy": "smallest source-backed slice",
            "handoff_expectation": "SpecWriter may use invalid fixtures as tests",
        },
        "spec_writer_brief": {
            "files_or_symbols": ["pycodestyle.py:parse_udiff"],
            "acceptance_targets": ["diff parser has contract tests."],
            "constraints": ["no source rewrite in architecture phase"],
            "contract_targets": [{"source": "pycodestyle.py:parse_udiff"}],
        },
        "source_context": {"pycodestyle.py:parse_udiff": {"signature": {"args": [], "returns": "dict"}}},
        "traceability": [{"source": "pycodestyle.py:parse_udiff", "target": "pycodestyle.py:parse_udiff"}],
        "risks": [
            {
                "severity": "medium",
                "description": "Malformed fixture input must stay isolated.",
                "impact": "Parser evidence could be mistaken for damaged source.",
                "mitigation": "Treat fixture syntax errors as test data.",
                "evidence_source": "testing/data/E12.py",
            }
        ],
        "open_questions": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

    report = red_team_architecture_decision(
        adr,
        {
            "content": {
                "source_health": {
                    "status": "damaged",
                    "syntax_error_count": 1,
                    "syntax_error_samples": [{"path": "docs/comment-example-code/example.py"}],
                }
            }
        },
    )

    assert "source_tree_requires_scope_decision" not in {row["code"] for row in report["blocking_findings"]}
