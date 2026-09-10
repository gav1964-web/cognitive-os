from __future__ import annotations
from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill
def _run_spec_writer(architecture_decision: dict):
    return run_role_skill(producer_for_artifact_type("TechnicalSpec"), architecture_decision=architecture_decision)

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
    assert none_spec["extraction_contract"]["output_contract"]["help_render"].startswith("HelpRenderResult")
    assert none_spec["extraction_contract"]["output_contract"]["failure_packet"].startswith("HelpFormattingFailure")


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
