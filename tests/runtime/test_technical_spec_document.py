from __future__ import annotations

from runtime.technical_spec_document import render_technical_spec_document
from runtime.technical_spec_builder import _extraction_contract, _rank_extraction_candidates
from runtime._parts import technical_spec_builder_part2 as spec_part2


def test_network_flow_is_deferred_below_local_property_context() -> None:
    ranked = _rank_extraction_candidates(
        [
            {"source": "entities.py:run_id", "kind": "pure_transform", "decorators": ["property"], "side_effects": []},
            {"source": "client.py:log_run", "kind": "central_flow_node", "side_effects": ["network"]},
        ]
    )

    assert ranked[0]["source"] == "entities.py:run_id"
    assert "external_effect_boundary" in " ".join(ranked[1]["reasons"])


def test_pass_only_hook_is_ranked_below_behavioral_candidate() -> None:
    ranked = _rank_extraction_candidates(
        [
            {"source": "plugin.py:empty_hook", "kind": "pure_transform", "snippet": "def empty_hook(app):\n    pass\n"},
            {"source": "plugin.py:clean_cache", "kind": "pure_transform", "snippet": "def clean_cache(app):\n    return app.clean()\n"},
        ]
    )

    assert ranked[0]["source"] == "plugin.py:clean_cache"
    assert "pass-only callable has no implementation contract" in ranked[1]["reasons"]


def test_class_declaration_is_ranked_below_its_executable_method() -> None:
    ranked = _rank_extraction_candidates(
        [
            {"source": "db.py:CursorWrapper", "node_kind": "class"},
            {"source": "db.py:execute", "snippet": "def execute(sql):\n    return cursor.execute(sql)\n"},
        ]
    )

    assert ranked[0]["source"] == "db.py:execute"
    assert "class declaration is context" in " ".join(ranked[1]["reasons"])


def test_bounded_policy_is_ranked_before_side_effecting_broad_flow() -> None:
    ranked = _rank_extraction_candidates(
        [
            {
                "source": "policy.py:can_run",
                "kind": "bounded_policy",
                "candidate_level": "bounded_policy",
                "candidate_score": 90,
                "signature": {"args": [{"name": "kind"}, {"name": "allowed"}], "returns": "bool"},
                "side_effects": ["observability"],
            },
            {"source": "runtime.py:run_forever", "kind": "broad_function", "side_effects": ["memory_state"]},
        ]
    )

    assert ranked[0]["source"] == "policy.py:can_run"


def test_extraction_contract_preserves_multi_file_effect_handoff() -> None:
    contract = _extraction_contract(
        [
            {
                "source": "signals.py:on_task_postrun",
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "None"},
                "snippet": "def on_task_postrun(payload):\n    publish(payload)\n",
                "side_effects": ["network"],
                "contract_slice_sources": ["signals.py:on_task_postrun", "service.py:publish"],
                "transitive_effect_chains": [
                    {"effect": "network", "call_chain": ["signals.py:on_task_postrun", "service.py:publish"]}
                ],
            }
        ],
        preferred_targets=["signals.py:on_task_postrun"],
    )

    assert contract["supporting_sources"] == ["service.py:publish"]
    assert contract["effect_handoff_chains"][0]["effect"] == "network"


def test_extraction_contract_preserves_promoted_selection_evidence(monkeypatch) -> None:
    def apply(ranked, **_kwargs):
        ranked[0]["selection_policy_ids"] = ["verified_policy"]
        return ranked

    monkeypatch.setattr(spec_part2, "apply_preflight_selection_policies", apply)
    contract = spec_part2._extraction_contract([{
        "source": "app.py:normalize",
        "signature": {"args": [{"name": "value", "annotation": "str"}]},
        "snippet": "def normalize(value):\n    return value.strip()\n",
        "side_effects": [],
    }])

    assert contract["selection_policy_ids"] == ["verified_policy"]


def test_preflight_policy_ranks_full_read_only_context_before_windowing(monkeypatch) -> None:
    observed_sizes = []

    def apply(ranked, **_kwargs):
        observed_sizes.append(len(ranked))
        reordered = sorted(ranked, key=lambda row: row["source"] != "other.py:challenger")
        reordered[0]["selection_policy_ids"] = ["learned_policy"]
        return reordered

    monkeypatch.setattr(spec_part2, "apply_preflight_selection_policies", apply)
    evidence = [{
        "source": f"app.py:candidate_{index}",
        "signature": {"args": [{"name": "value"}]},
        "snippet": f"def candidate_{index}(value):\n    return value\n",
    } for index in range(10)]
    evidence.append({
        "source": "other.py:challenger",
        "signature": {"args": [{"name": "value"}]},
        "snippet": "def challenger(value):\n    return value\n",
    })

    contract = spec_part2._extraction_contract(
        evidence,
        preferred_targets=["app.py:candidate_0"],
    )

    assert max(observed_sizes) > 1
    assert contract["candidate"] == "other.py:challenger"


def test_technical_spec_document_renders_human_tz_sections() -> None:
    text = render_technical_spec_document(
        project_report={"project": "demo", "content": {"summary": {"root": "demo"}}},
        architecture_decision={"goal": "Extract parser", "project": "demo"},
        technical_spec={
            "artifact_type": "TechnicalSpec",
            "chosen_architecture_option": "minimal_safe_extraction",
            "scope": ["Prepare parser contract."],
            "requirements": [
                {
                    "id": "REQ-001",
                    "priority": "MUST",
                    "statement": "parser.py:parse must expose a bounded contract.",
                    "source": "parser.py:parse",
                }
            ],
            "extraction_contract": {
                "candidate": "parser.py:parse",
                "candidate_score": 120,
                "selection_reason": "source-backed parser boundary",
                "semantic_quality": {
                    "status": "strong",
                    "score": 94,
                    "reasons": ["candidate name suggests a bounded contract"],
                },
            },
            "work_plan_contract": {
                "status": "ready",
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "name": "parser_contract_slice",
                "goal": "Define parser contract before implementation.",
                "targets": ["parser.py:parse"],
                "obligations": [
                    {
                        "id": "WPC-001",
                        "step": "Define ParserInput and ParserOutput contracts.",
                        "target": "parser.py:parse",
                        "verification": "must be linked to acceptance criteria",
                    }
                ],
            },
            "interface_contracts": [
                {
                    "source": "parser.py:parse",
                    "input_contract": {"text": "str"},
                    "output_contract": {"result": "dict"},
                    "side_effect_policy": {"declared": [], "retry_policy": "safe to retry if pure contract holds"},
                }
            ],
            "data_lifecycle": [
                {
                    "stage": "input",
                    "shape": "raw text",
                    "contract_expectation": "validate before parse",
                    "evidence": "ProjectMapReport",
                }
            ],
            "error_model": [
                {"error": "bad_input", "handling": "return typed error", "source": "parser.py:parse"}
            ],
            "acceptance_criteria": [
                {
                    "id": "AC-001",
                    "criterion": "parser.py:parse returns dict for valid text.",
                    "verification": "pytest",
                    "source": "parser.py:parse",
                }
            ],
            "traceability_table": [
                {"source": "parser.py:parse", "requirement": "contract required", "acceptance_id": "AC-001"}
            ],
            "state_and_replay_policy": [
                {
                    "owner": "execution_inputs",
                    "kind": "reproducibility_state",
                    "lifetime": "scenario_replay",
                    "resume_policy": "persist input",
                }
            ],
            "verification_strategy": {"contract_tests": [], "negative_tests": [], "replay_checks": []},
            "implementation_handoff": {
                "recommended_role": "implementer",
                "expected_output": "ImplementationPlan",
                "patch_scope": ["parser.py:parse"],
            },
            "constraints": ["no source rewrite in spec phase"],
            "non_goals": ["do not rewrite whole project"],
        },
    )

    assert "# Техническое задание" in text
    assert "## Первый рабочий срез" in text
    assert "parser_contract_slice" in text
    assert "## Связанные interface contracts" in text
    assert "parser.py:parse" in text
    assert "## Модель ошибок" in text
    assert "## Критерии приемки" in text
    assert "Семантическое качество: сильный кандидат (94)" in text
    assert "Рекомендуемая роль: implementer" in text


def test_technical_spec_document_explains_inner_contract_vs_workflow_slice() -> None:
    text = render_technical_spec_document(
        project_report={"project": "demo", "content": {"summary": {"root": "demo"}}},
        architecture_decision={"goal": "Extract safe inner capability", "project": "demo"},
        technical_spec={
            "chosen_architecture_option": "minimal_safe_extraction",
            "scope": ["Prepare one capability contract."],
            "extraction_contract": {
                "candidate": "llm_providers.py:build_providers",
                "candidate_score": 124,
                "selection_reason": "pure transform candidate",
                "semantic_quality": {"status": "strong", "score": 100, "reasons": []},
            },
            "work_plan_contract": {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "name": "chat_completion_proxy_slice",
                "goal": "Stabilize request workflow.",
                "targets": ["api_server.py:chat_completions", "api_server.py:_handle_chat_request"],
                "obligations": [
                    {
                        "id": "WPC-001",
                        "step": "Define RequestEnvelope.",
                        "target": "api_server.py:chat_completions",
                        "verification": "review checklist",
                    }
                ],
            },
            "interface_contracts": [],
        },
    )

    assert "целевая функция выбрана как самый безопасный внутренний capability" in text
    assert "первый рабочий срез показывает более широкий пользовательский workflow" in text
