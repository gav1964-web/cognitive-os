from __future__ import annotations

from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill


def _run_spec_writer(architecture_decision: dict):
    return run_role_skill(producer_for_artifact_type("TechnicalSpec"), architecture_decision=architecture_decision)


def test_spec_writer_demotes_constructor_logging_and_generic_predicate_targets():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate low-value first-slice target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/worker/base.py:__init__",
                "pkg/__init__.py:configure_logging",
                "pkg/queries.py:all",
                "pkg/providers/factory.py:build_providers_from_config",
            ],
        },
        "traceability": [
            {"source": "pkg/worker/base.py:__init__", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/__init__.py:configure_logging", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/queries.py:all", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "pkg/providers/factory.py:build_providers_from_config",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "pkg/worker/base.py:__init__": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "self", "annotation": "Any"}], "returns": "None"},
                "snippet": {"text": "def __init__(self): ..."},
            },
            "pkg/__init__.py:configure_logging": {
                "kind": "central_flow_node",
                "signature": {"args": [], "returns": "None"},
                "snippet": {"text": "def configure_logging(): ..."},
            },
            "pkg/queries.py:all": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "items", "annotation": "list"}], "returns": "bool"},
                "snippet": {"text": "def all(items): ..."},
            },
            "pkg/providers/factory.py:build_providers_from_config": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "config", "annotation": "dict"}], "returns": "list[Provider]"},
                "snippet": {"text": "def build_providers_from_config(config): ..."},
                "callers": ["pkg/api.py:create_app"],
                "central_flow_node": {"call_count": 6},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/providers/factory.py:build_providers_from_config"
    assert spec["extraction_contract"]["semantic_quality"]["status"] == "strong"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    low_value_reasons = " ".join(ranked["pkg/worker/base.py:__init__"]["reasons"])
    assert "constructor/logging/config helper" in low_value_reasons


def test_spec_writer_keeps_selected_candidate_in_interface_contracts_when_many_targets():
    sources = [f"pkg/mod.py:helper_{index}" for index in range(20)]
    selected = "pkg/core.py:parse_payload"
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Keep selected candidate handoff contract visible",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [*sources, selected],
            "contract_targets": [{"source": source} for source in [*sources, selected]],
        },
        "traceability": [
            {"source": source, "requirement": "Capability candidate requires TechnicalSpec."}
            for source in [*sources, selected]
        ],
        "source_context": {
            **{
                source: {
                    "kind": "unknown",
                    "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "dict"},
                    "snippet": {"text": "def helper(payload): ..."},
                }
                for source in sources
            },
            selected: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "ParsedPayload"},
                "snippet": {"text": "def parse_payload(payload): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == selected
    assert spec["interface_contracts"][0]["source"] == selected


def test_spec_writer_demotes_liveness_probe_when_domain_target_exists():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Avoid health endpoint as first contract",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["api.py:health", "api.py:list_provider_capabilities"],
        },
        "traceability": [
            {"source": "api.py:health", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "api.py:list_provider_capabilities", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "api.py:health": {
                "kind": "unknown",
                "signature": {"args": [], "returns": "dict"},
                "snippet": {"text": "def health(): return {'ok': True}"},
            },
            "api.py:list_provider_capabilities": {
                "kind": "unknown",
                "signature": {"args": [], "returns": "list[ProviderCapability]"},
                "snippet": {"text": "def list_provider_capabilities(): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "api.py:list_provider_capabilities"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "health/status/ping probe" in " ".join(ranked["api.py:health"]["reasons"])


def test_spec_writer_prefers_read_query_contract_over_write_operation():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate mutation target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["tinydb/storages.py:write", "tinydb/table.py:search"],
        },
        "traceability": [
            {"source": "tinydb/storages.py:write", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "tinydb/table.py:search", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "tinydb/storages.py:write": {
                "kind": "unknown",
                "signature": {"args": [{"name": "data", "annotation": "dict"}], "returns": "None"},
                "snippet": {"text": "def write(data): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
            "tinydb/table.py:search": {
                "kind": "unknown",
                "signature": {"args": [{"name": "cond", "annotation": "QueryLike"}], "returns": "list[Document]"},
                "snippet": {"text": "def search(cond): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "tinydb/table.py:search"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    write_reasons = " ".join(ranked["tinydb/storages.py:write"]["reasons"])
    assert "write/update/delete operation" in write_reasons


def test_spec_writer_does_not_promote_weak_first_slice_over_strong_core_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Avoid weak first-slice override",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "request_boundary_slice",
            "targets": ["app/api/handlers.py:handle_chat(186 loc)", "app/providers/factory.py:build_providers_from_config"],
            "steps": ["Define request envelope.", "Keep provider selection pure."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "app/api/handlers.py:handle_chat",
                "app/providers/factory.py:build_providers_from_config",
            ],
        },
        "traceability": [
            {"source": "app/api/handlers.py:handle_chat", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "app/providers/factory.py:build_providers_from_config",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "app/api/handlers.py:handle_chat": {
                "kind": "broad_function",
                "signature": {
                    "args": [{"name": "request", "annotation": "LegacyChatRequest"}],
                    "returns": "",
                },
                "snippet": {"text": "def handle_chat(request): ..."},
                "side_effects": ["database"],
            },
            "app/providers/factory.py:build_providers_from_config": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "app_config", "annotation": "AppConfig"}], "returns": "dict[str, Provider]"},
                "snippet": {"text": "def build_providers_from_config(app_config): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "app/providers/factory.py:build_providers_from_config"
    assert spec["extraction_contract"]["input_contract"] == {"app_config": "AppConfig"}
    assert spec["extraction_contract"]["output_contract"] == {"result": "dict[str, Provider]"}


def test_spec_writer_prefers_multi_agent_consensus_first_slice_over_local_validator():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Stabilize multi-agent orchestration",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "agent_consensus_orchestration_slice",
            "targets": [
                "core/consensus/engine.py:run_consensus(134 loc)",
                "core/orchestrator/orchestrator.py:_execute_group(90 loc)",
            ],
            "steps": ["Define ConsensusInput.", "Normalize AgentResponse.", "Record AgentFailurePacket."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "core/consensus/engine.py:run_consensus",
                "core/orchestrator/orchestrator.py:_execute_group",
                "agents/tz_group/tz_analyst_agent.py:_validate_requirements",
            ],
        },
        "traceability": [
            {"source": "core/consensus/engine.py:run_consensus", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "agents/tz_group/tz_analyst_agent.py:_validate_requirements", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "core/consensus/engine.py:run_consensus": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "task", "annotation": "A2ATask"}], "returns": "Any"},
                "snippet": {"text": "async def run_consensus(task): ..."},
            },
            "core/orchestrator/orchestrator.py:_execute_group": {
                "kind": "unknown",
                "signature": {"args": [{"name": "group", "annotation": "GroupConfig"}], "returns": "dict"},
                "snippet": {"text": "async def _execute_group(group): ..."},
            },
            "agents/tz_group/tz_analyst_agent.py:_validate_requirements": {
                "kind": "unknown",
                "signature": {"args": [{"name": "task_data", "annotation": "Dict[str, Any]"}], "returns": "Dict[str, Any]"},
                "snippet": {"text": "def _validate_requirements(task_data): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "core/consensus/engine.py:run_consensus"
    assert spec["extraction_contract"]["contract_family"] == "agent_consensus_orchestration_boundary"
    assert "ConsensusInput" in spec["extraction_contract"]["input_contract"]["consensus_input"]


def test_spec_writer_prefers_ml_generation_boundary_over_ad_hoc_evaluator():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Stabilize ML competition inference",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "ml_inference_submission_slice",
            "targets": ["x31.py:generate_response", "x31.py:postprocess", "x31.py:evaluate"],
            "steps": ["Define PromptRow.", "Inject fake model adapter.", "Verify submission row."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable ML inference TechnicalSpec."],
            "files_or_symbols": ["x31.py:generate_response", "x31.py:postprocess", "x31.py:evaluate"],
        },
        "traceability": [
            {"source": "x31.py:generate_response", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "x31.py:evaluate", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "x31.py:generate_response": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "prompt", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def generate_response(prompt): return tokenizer.decode(model.generate(...))"},
            },
            "x31.py:postprocess": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "response", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def postprocess(response): return response.strip()"},
            },
            "x31.py:evaluate": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "query", "annotation": ""}, {"name": "answer", "annotation": ""}], "returns": ""},
                "snippet": {
                    "text": (
                        "def evaluate(query, answer):\n"
                        "    response = pipe(query, answer)\n"
                        "    return output[0]['score']"
                    )
                },
            },
        },
    }

    spec = _run_spec_writer(adr)
    contract = spec["extraction_contract"]

    assert contract["candidate"] == "x31.py:generate_response"
    assert contract["contract_family"] == "ml_generation_boundary"
    ranked = {row["source"]: row for row in contract["ranked_candidates"]}
    assert "ML inference/submission boundary" in " ".join(ranked["x31.py:generate_response"]["reasons"])
    assert "ad-hoc evaluator" in " ".join(ranked["x31.py:evaluate"]["reasons"])
    assert "unresolved names" in " ".join(ranked["x31.py:evaluate"]["reasons"])


def test_spec_writer_demotes_snippet_with_high_confidence_unresolved_names():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Pick a reliable first slice",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable TechnicalSpec."],
            "files_or_symbols": ["app/eval.py:evaluate", "app/transforms.py:normalize_record"],
        },
        "traceability": [
            {"source": "app/eval.py:evaluate", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "app/transforms.py:normalize_record", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "app/eval.py:evaluate": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "query", "annotation": "str"}], "returns": "float"},
                "candidate_level": "core_flow",
                "candidate_score": 95,
                "snippet": {
                    "text": (
                        "def evaluate(query):\n"
                        "    response = pipe(query)\n"
                        "    return float(output[0]['score'])"
                    )
                },
            },
            "app/transforms.py:normalize_record": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "record", "annotation": "dict"}], "returns": "dict"},
                "candidate_level": "supporting_transform",
                "candidate_score": 40,
                "snippet": {"text": "def normalize_record(record):\n    return {str(k): v for k, v in record.items()}"},
            },
        },
    }

    spec = _run_spec_writer(adr)
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}

    assert spec["extraction_contract"]["candidate"] == "app/transforms.py:normalize_record"
    assert "unresolved names" in " ".join(ranked["app/eval.py:evaluate"]["reasons"])


def test_spec_writer_infers_contracts_for_any_and_none_returns():
    any_return_adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Infer contracts for untyped Python functions",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["httpie/cli/nested_json/interpret.py:interpret"],
        },
        "traceability": [
            {"source": "httpie/cli/nested_json/interpret.py:interpret", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "httpie/cli/nested_json/interpret.py:interpret": {
                "kind": "pure_transform",
                "signature": {
                    "args": [
                        {"name": "context", "annotation": "str"},
                        {"name": "key", "annotation": "str"},
                        {"name": "value", "annotation": ""},
                    ],
                    "returns": "Any",
                },
                "snippet": {"text": "def interpret(context, key, value): return {'key': value}"},
            },
        },
    }
    none_return_adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Infer contracts for None-return render helper",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["typer/rich_utils.py:rich_format_help"],
        },
        "traceability": [
            {"source": "typer/rich_utils.py:rich_format_help", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "typer/rich_utils.py:rich_format_help": {
                "kind": "broad_function",
                "signature": {"args": [], "returns": "None"},
                "snippet": {"text": "def rich_format_help(): yield panel"},
            },
        },
    }

    any_spec = _run_spec_writer(any_return_adr)
    none_spec = _run_spec_writer(none_return_adr)

    assert any_spec["extraction_contract"]["candidate"] == "httpie/cli/nested_json/interpret.py:interpret"
    assert any_spec["extraction_contract"]["input_contract"]["value"] == "InferredValue"
    assert any_spec["extraction_contract"]["output_contract"] == {"result": "ParsedStructure"}
    assert none_spec["extraction_contract"]["candidate"] == "typer/rich_utils.py:rich_format_help"
    assert none_spec["extraction_contract"]["output_contract"] == {"result": "FormattedHelpRenderable"}


def test_spec_writer_prefers_database_search_over_generic_get_and_storage_adapter():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate database domain target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "tinydb/table.py:get",
                "tinydb/table.py:search",
                "tinydb/storages.py:read",
            ],
        },
        "traceability": [
            {"source": "tinydb/table.py:get", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "tinydb/table.py:search", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "tinydb/storages.py:read", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "tinydb/table.py:get": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "doc_id", "annotation": "int"}], "returns": "Document | None"},
                "snippet": {"text": "def get(doc_id): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 96,
            },
            "tinydb/table.py:search": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "cond", "annotation": "QueryLike"}], "returns": "list[Document]"},
                "snippet": {"text": "def search(cond): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
            "tinydb/storages.py:read": {
                "kind": "central_flow_node",
                "signature": {"args": [], "returns": "dict"},
                "snippet": {"text": "def read(): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 94,
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "tinydb/table.py:search"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    search_reasons = " ".join(ranked["tinydb/table.py:search"]["reasons"])
    get_reasons = " ".join(ranked["tinydb/table.py:get"]["reasons"])
    storage_reasons = " ".join(ranked["tinydb/storages.py:read"]["reasons"])
    assert "query/condition contract" in search_reasons
    assert "generic accessor" in get_reasons
    assert "storage adapter" in storage_reasons


def test_spec_writer_prefers_repair_contract_surface_over_generated_output():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate repair-loop target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable repair-loop TechnicalSpec."],
            "files_or_symbols": [
                "autofix_docker/generated_v2/pipeline.py:extract_reviews_from_page",
                "autofix_docker/module_contract_checker.py:check_single_module_output",
                "autofix_docker/goal_to_spec.py:goal_to_spec",
            ],
        },
        "traceability": [
            {"source": "autofix_docker/generated_v2/pipeline.py:extract_reviews_from_page", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "autofix_docker/module_contract_checker.py:check_single_module_output", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "autofix_docker/goal_to_spec.py:goal_to_spec", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "autofix_docker/generated_v2/pipeline.py:extract_reviews_from_page": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "url", "annotation": "str"}], "returns": "List[Review]"},
                "snippet": {"text": "def extract_reviews_from_page(url): ..."},
            },
            "autofix_docker/module_contract_checker.py:check_single_module_output": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "module_name", "annotation": "str"}], "returns": "dict"},
                "snippet": {"text": "def check_single_module_output(module_name): ..."},
            },
            "autofix_docker/goal_to_spec.py:goal_to_spec": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "goal", "annotation": "str"}], "returns": "dict"},
                "snippet": {"text": "def goal_to_spec(goal): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "autofix_docker/module_contract_checker.py:check_single_module_output"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "module contract checker" in " ".join(ranked["autofix_docker/module_contract_checker.py:check_single_module_output"]["reasons"])
    assert "generated project output" in " ".join(ranked["autofix_docker/generated_v2/pipeline.py:extract_reviews_from_page"]["reasons"])


def test_spec_writer_shapes_llm_repair_hypothesis_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate repair-loop contract shape",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable repair-loop TechnicalSpec."],
            "files_or_symbols": [
                "AutoFix/auto_dev_agent.py:send_to_model",
                "AutoFix/auto_dev_agent.py:write_files",
                "AutoFix/auto_dev_agent.py:docker_run",
            ],
            "first_slice": {
                "name": "repair_attempt_contract_slice",
                "knowledge_rule": "llm_auto_repair_loop",
                "targets": [
                    "AutoFix/auto_dev_agent.py:send_to_model",
                    "AutoFix/auto_dev_agent.py:write_files",
                    "AutoFix/auto_dev_agent.py:docker_run",
                ],
                "steps": ["Define repair contracts.", "Validate model JSON.", "Verify in Docker."],
            },
        },
        "traceability": [
            {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "requirement": "Define repair contracts.",
                "target": "AutoFix/auto_dev_agent.py:send_to_model",
            }
        ],
        "source_context": {
            "AutoFix/auto_dev_agent.py:send_to_model": {
                "kind": "unknown",
                "signature": {"args": [{"name": "error_text", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def send_to_model(self, error_text): ..."},
                "side_effects": ["filesystem", "memory_state"],
            },
            "AutoFix/auto_dev_agent.py:write_files": {
                "kind": "unknown",
                "signature": {"args": [{"name": "updates", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def write_files(self, updates): ..."},
                "side_effects": ["filesystem"],
            },
            "AutoFix/auto_dev_agent.py:docker_run": {
                "kind": "unknown",
                "signature": {"args": [], "returns": ""},
                "snippet": {"text": "def docker_run(self): ..."},
                "side_effects": ["subprocess", "memory_state"],
            },
        },
    }

    spec = _run_spec_writer(adr)
    contract = spec["extraction_contract"]

    assert contract["candidate"] == "AutoFix/auto_dev_agent.py:send_to_model"
    assert contract["semantic_quality"]["status"] == "strong"
    assert contract["contract_family"] == "llm_repair_hypothesis_boundary"
    assert "failure_evidence" in contract["input_contract"]
    assert "model_patch_proposal" in contract["output_contract"]
    assert "invalid_model_json" in contract["failure_modes"]
    assert contract["side_effects"]["requires_validation_gate"] is True


def test_spec_writer_prefers_representative_lifecycle_slice_over_domain_utility():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate representative domain slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap",
                "spyder/api/widgets/main_widget.py:create_window",
            ],
        },
        "traceability": [
            {"source": "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "spyder/api/widgets/main_widget.py:create_window", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap": {
                "kind": "unknown",
                "signature": {
                    "args": [
                        {"name": "svg", "annotation": "str"},
                        {"name": "scale", "annotation": "float"},
                    ],
                    "returns": "QPixmap",
                },
                "snippet": {"text": "def svg_to_scaled_pixmap(svg, scale): ..."},
            },
            "spyder/api/widgets/main_widget.py:create_window": {
                "kind": "unknown",
                "signature": {"args": [], "returns": "QMainWindow"},
                "snippet": {"text": "def create_window(): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "spyder/api/widgets/main_widget.py:create_window"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    lifecycle_reasons = " ".join(ranked["spyder/api/widgets/main_widget.py:create_window"]["reasons"])
    utility_reasons = " ".join(ranked["spyder/api/widgets/mixins.py:svg_to_scaled_pixmap"]["reasons"])
    assert "representative domain flow/lifecycle slice" in lifecycle_reasons
    assert "domain utility/helper" in utility_reasons


def test_spec_writer_demotes_request_dispatcher_boundary():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate transport project first slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable transport capability extraction spec."],
            "files_or_symbols": [
                "httpcore/_async/http2.py:handle_async_request",
                "httpcore/_async/socks_proxy.py:_init_socks5_connection",
            ],
        },
        "traceability": [
            {
                "source": "httpcore/_async/http2.py:handle_async_request",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
            {
                "source": "httpcore/_async/socks_proxy.py:_init_socks5_connection",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "httpcore/_async/http2.py:handle_async_request": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "request", "annotation": "Request"}], "returns": "Response"},
                "snippet": {"text": "async def handle_async_request(request): ..."},
            },
            "httpcore/_async/socks_proxy.py:_init_socks5_connection": {
                "kind": "unknown",
                "signature": {
                    "args": [{"name": "stream", "annotation": "AsyncNetworkStream"}],
                    "returns": "AsyncNetworkStream",
                },
                "snippet": {"text": "async def _init_socks5_connection(stream): ..."},
                "callers": ["httpcore/_async/socks_proxy.py:handle_async_request"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "httpcore/_async/socks_proxy.py:_init_socks5_connection"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    dispatcher_reasons = " ".join(ranked["httpcore/_async/http2.py:handle_async_request"]["reasons"])
    assert "request dispatcher boundary" in dispatcher_reasons


def test_spec_writer_demotes_path_accessor_over_validator_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate build backend first slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable build capability extraction spec."],
            "files_or_symbols": [
                "src/build/_builder.py:metadata_path",
                "src/build/__main__.py:_validate_sdist_archive",
            ],
        },
        "traceability": [
            {"source": "src/build/_builder.py:metadata_path", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "src/build/__main__.py:_validate_sdist_archive",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "src/build/_builder.py:metadata_path": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "name", "annotation": "str"}], "returns": "Path"},
                "snippet": {"text": "def metadata_path(name): ..."},
            },
            "src/build/__main__.py:_validate_sdist_archive": {
                "kind": "unknown",
                "signature": {"args": [{"name": "path", "annotation": "Path"}], "returns": "None"},
                "snippet": {"text": "def _validate_sdist_archive(path): ..."},
                "callers": ["src/build/__main__.py:_build"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "src/build/__main__.py:_validate_sdist_archive"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    accessor_reasons = " ".join(ranked["src/build/_builder.py:metadata_path"]["reasons"])
    assert "small helper is less representative" in accessor_reasons


def test_spec_writer_demotes_operational_lifecycle_wrapper_over_builder_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate package operation first slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/commands/install.py:install",
                "pkg/auth/digest.py:build_digest_header",
            ],
        },
        "traceability": [
            {"source": "pkg/commands/install.py:install", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/auth/digest.py:build_digest_header", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "pkg/commands/install.py:install": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "options", "annotation": "InstallOptions"}], "returns": "None"},
                "snippet": {"text": "def install(options): ..."},
            },
            "pkg/auth/digest.py:build_digest_header": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "challenge", "annotation": "dict"}], "returns": "str"},
                "snippet": {"text": "def build_digest_header(challenge): ..."},
                "callers": ["pkg/sessions.py:request"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/auth/digest.py:build_digest_header"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    install_reasons = " ".join(ranked["pkg/commands/install.py:install"]["reasons"])
    assert "operational lifecycle/mutation wrapper" in install_reasons


def test_spec_writer_semantic_rerank_prefers_stronger_bounded_slice_when_close():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate semantic rerank",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/worker.py:process_everything",
                "pkg/contracts.py:parse_payload",
            ],
        },
        "traceability": [
            {"source": "pkg/worker.py:process_everything", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/contracts.py:parse_payload", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "pkg/worker.py:process_everything": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "dict"},
                "snippet": {"text": "def process_everything(payload): ..."},
                "central_flow_node": True,
                "candidate_score": 100,
            },
            "pkg/contracts.py:parse_payload": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "text", "annotation": "str"}], "returns": "Payload"},
                "snippet": {"text": "def parse_payload(text): ..."},
                "side_effects": ["filesystem_read"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/contracts.py:parse_payload"
    assert spec["extraction_contract"]["semantic_quality"]["status"] == "strong"
    assert "semantic rerank selected" in spec["extraction_contract"]["selection_reason"]


def test_spec_writer_blocks_when_first_slice_has_no_safe_targets_and_only_tests_are_available():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Do not build a spec from test-only evidence",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "automation_task_execution_slice",
            "goal": "No Python implementation target exists.",
            "targets": [],
            "steps": ["Define contract only if a source-backed target exists."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["test/test_default.py:test_default_not_callable"],
            "first_slice": {
                "name": "automation_task_execution_slice",
                "goal": "No Python implementation target exists.",
                "targets": [],
                "steps": ["Define contract only if a source-backed target exists."],
            },
        },
        "traceability": [
            {"source": "test/test_default.py:test_default_not_callable", "requirement": "Capability candidate requires TechnicalSpec."}
        ],
        "source_context": {
            "test/test_default.py:test_default_not_callable": {
                "kind": "test_function",
                "signature": {"args": [], "returns": "None"},
                "snippet": {"text": "def test_default_not_callable(): ..."},
            }
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["work_plan_contract"]["status"] == "blocked_no_first_slice"
    assert spec["extraction_contract"]["status"] == "blocked_no_safe_candidate"
    assert spec["extraction_contract"]["candidate"] is None
    assert spec["source_evidence"] == []
