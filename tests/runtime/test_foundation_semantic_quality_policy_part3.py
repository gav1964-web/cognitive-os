from __future__ import annotations

from runtime.foundation_semantic_quality import evaluate_foundation_semantic_quality


TARGET = "src/ansiblelint/runner.py:_get_ansible_syntax_check_matches"


def _foundation_payload() -> dict:
    project = {
        "summary": {"root": "ansible-lint", "frameworks": [], "entrypoints": ["src/ansiblelint/__main__.py:main"]},
        "answers": {
            "1_scope": {
                "main_task": "ansible-lint checks playbooks and YAML rule syntax for practices that could be improved.",
                "supported_scenarios": ["lint playbooks", "run syntax checks"],
                "inputs": ["playbook files", "lint configuration"],
                "outputs": ["rule matches", "syntax-check diagnostics"],
                "domain_profile": {"kind": "automation_engine", "confidence": 0.71, "evidence": ["ansible", "playbook", "yaml"]},
            },
            "2_execution": {"primary_execution_path": [TARGET]},
            "3_capabilities": {"atomic_reusable_capabilities": [TARGET]},
            "4_contracts_data": {"main_data_structures": ["Lintable", "MatchError"], "weak_contract_zones": []},
            "5_errors_state_repro": {
                "likely_error_types": ["syntax check failure"],
                "state_to_preserve": ["playbook path", "rule id"],
                "minimal_cognitive_loop": ["collect", "run syntax check", "emit matches"],
            },
            "6_runtime_extraction_readiness": {
                "data_lifecycle": [{"stage": "collect"}, {"stage": "check"}, {"stage": "report"}],
                "minimal_extraction_plan": {"capabilities_to_extract": [{"capability": TARGET, "reason": "bounded syntax check mapping"}]},
            },
        },
        "evidence_summary": {"source_refs": [TARGET, "src/ansiblelint/app.py", "src/ansiblelint/rules/jinja.py"]},
    }
    return {
        "artifacts": {
            "project_map_report": project,
            "architecture_decision": {
                "decision_summary": "Select ansible syntax-check match extraction as the first bounded lint contract.",
                "architecture_synthesis": {"project_profile": {"archetype": "automation_engine", "domain_profile_kind": "automation_engine"}},
                "first_slice_contract": {"name": "syntax_check_slice", "targets": [TARGET]},
                "architecture_options": [{"id": "syntax_check"}, {"id": "rule_rewrite"}],
                "rejected_options": [{"id": "rule_rewrite"}],
                "spec_writer_brief": {"files_or_symbols": [TARGET], "contract_targets": [TARGET], "acceptance_targets": ["syntax errors map to lint matches"]},
                "risks": [{"risk": "Subprocess output can drift by ansible version.", "mitigation": "Normalize stderr/stdout fixtures."}],
                "fact_judgment_ledger": {
                    "facts": [{"claim": "runner target exists"}],
                    "judgments": [{"judgment": "syntax-check mapping is bounded", "validation_gate": "fixture tests"}],
                },
                "source_context": {TARGET: {}, "src/ansiblelint/app.py": {}, "src/ansiblelint/rules/jinja.py": {}},
                "open_questions": [],
                "non_goals": ["Do not change rule semantics."],
            },
            "technical_spec": {},
        }
    }


def test_domain_backed_lint_purpose_survives_generic_tail_phrase() -> None:
    quality = evaluate_foundation_semantic_quality(_foundation_payload())

    assert "project_analyzer.purpose_is_specific" not in quality["warnings"]


def test_domain_backed_lint_purpose_still_requires_source_evidence() -> None:
    payload = _foundation_payload()
    project = payload["artifacts"]["project_map_report"]
    project["evidence_summary"] = {"source_refs": []}

    quality = evaluate_foundation_semantic_quality(payload)

    assert "project_analyzer.purpose_is_specific" in quality["warnings"]
