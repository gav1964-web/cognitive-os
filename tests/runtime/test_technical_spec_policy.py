from __future__ import annotations

from runtime._parts.technical_spec_builder_part3 import _input_contract_from_signature
from runtime.source_target_policy import is_context_only_implementation_target, load_role_source_policy
from runtime.technical_spec_builder import build_technical_spec
from runtime.technical_spec_policy import load_technical_spec_policy


def test_technical_spec_policy_loads_required_sections():
    policy = load_technical_spec_policy()
    source_policy = load_role_source_policy()

    assert policy["schema_version"] == "technical_spec_policy.v1"
    assert source_policy["implementation_target_policy"]["context_only_path_tokens"]
    assert "context_only_source_path_tokens" not in policy
    assert policy["snippet_analysis"]["allowed_external_names"]
    assert policy["contract_type_inference"]["argument_rules"]
    assert policy["semantic_rerank"]["scan_limit"] >= 2
    assert is_context_only_implementation_target("python/pkg/_vendor/dataclasses.py:_get_field")


def test_technical_spec_policy_drives_contract_type_inference_and_source_scope():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Extract parser",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare parser contract."],
                "files_or_symbols": ["docs/example.py:parse_payload", "src/parser.py:parse_payload"],
            },
            "traceability": [
                {"source": "docs/example.py:parse_payload", "requirement": "Capability candidate requires TechnicalSpec."},
                {"source": "src/parser.py:parse_payload", "requirement": "Capability candidate requires TechnicalSpec."},
            ],
            "source_context": {
                "docs/example.py:parse_payload": {
                    "kind": "pure_transform",
                    "signature": {"args": [{"name": "payload", "annotation": "Any"}], "returns": "Any"},
                    "snippet": {"text": "def parse_payload(payload): return {'ok': True}"},
                },
                "src/parser.py:parse_payload": {
                    "kind": "pure_transform",
                    "signature": {"args": [{"name": "payload", "annotation": "Any"}], "returns": "Any"},
                    "snippet": {"text": "def parse_payload(payload): return {'ok': True}"},
                },
            },
        }
    )

    assert spec["extraction_contract"]["candidate"] == "src/parser.py:parse_payload"
    assert spec["extraction_contract"]["input_contract"] == {"payload": "MappingLike"}
    assert spec["extraction_contract"]["output_contract"] == {"result": "ParsedStructure"}
    assert all(not row["source"].startswith("docs/") for row in spec["source_evidence"])


def test_technical_spec_policy_keeps_runtime_package_named_testing():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Prepare zope.testing form parser contract",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare form parser contract."],
                "files_or_symbols": ["src/zope/testing/formparser.py:parse"],
                "first_slice": {"targets": ["src/zope/testing/formparser.py:parse"]},
            },
            "source_context": {
                "src/zope/testing/formparser.py:parse": {
                    "kind": "pure_transform",
                    "signature": {"args": [{"name": "data", "annotation": "str"}], "returns": "Any"},
                    "snippet": {"text": "def parse(data):\n    return FormParser(data).parse()\n"},
                },
            },
        }
    )

    assert spec["extraction_contract"]["candidate"] == "src/zope/testing/formparser.py:parse"
    assert spec["source_evidence"]


def test_technical_spec_recovers_work_plan_from_selected_candidate():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Prepare doctest execution contract",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare doctest contract."],
                "files_or_symbols": ["src/zope/testing/doctestcase.py:_run_test"],
                "first_slice": {"name": "empty_slice", "targets": []},
            },
            "source_context": {
                "src/zope/testing/doctestcase.py:_run_test": {
                    "kind": "unknown",
                    "signature": {"args": [{"name": "test"}]},
                    "snippet": {"text": "def _run_test(test):\n    return None\n"},
                },
            },
        }
    )

    assert spec["extraction_contract"]["candidate"] == "src/zope/testing/doctestcase.py:_run_test"
    assert spec["work_plan_contract"]["status"] == "ready"
    assert spec["work_plan_contract"]["targets"] == ["src/zope/testing/doctestcase.py:_run_test"]


def test_architecture_policy_keeps_runtime_package_named_testing():
    from runtime.architecture_decision_policy import load_architecture_decision_policy
    from runtime.project_architecture_knowledge import load_architecture_knowledge

    policy = load_architecture_decision_policy()
    source_selection = policy["source_selection"]
    scope_policy = load_architecture_knowledge()["source_scope_policy"]

    assert "/testing/" not in source_selection["context_only_path_tokens"]
    assert "/testing/" not in source_selection["callable_transform_fallback"]["excluded_path_tokens"]
    assert "testing" not in scope_policy["context_only_parts"]


def test_technical_spec_policy_drives_unresolved_snippet_penalty():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Avoid ad-hoc evaluator",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare generation contract."],
                "files_or_symbols": ["x31.py:evaluate", "x31.py:generate_response"],
            },
            "traceability": [
                {"source": "x31.py:evaluate", "requirement": "Capability candidate requires TechnicalSpec."},
                {"source": "x31.py:generate_response", "requirement": "Capability candidate requires TechnicalSpec."},
            ],
            "source_context": {
                "x31.py:evaluate": {
                    "kind": "pure_transform",
                    "signature": {"args": [], "returns": "dict"},
                    "snippet": {"text": "def evaluate():\n    return pipe(output)\n"},
                },
                "x31.py:generate_response": {
                    "kind": "pure_transform",
                    "signature": {"args": [{"name": "prompt_text", "annotation": "str"}], "returns": "str"},
                    "snippet": {"text": "def generate_response(prompt_text):\n    return str(prompt_text)\n"},
                },
            },
        }
    )

    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "snippet references unresolved names" in " ".join(ranked["x31.py:evaluate"]["reasons"])


def test_technical_spec_input_contract_uses_kwonly_and_skips_self():
    contract = _input_contract_from_signature(
        {
            "args": [{"name": "self"}, {"name": "payload", "annotation": "dict"}],
            "kwonlyargs": [{"name": "limit", "annotation": "int"}],
        },
        None,
    )

    assert contract == {"payload": "dict", "limit": "int"}


def test_technical_spec_reconciles_semantic_profile_with_signature_contract():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Prepare framework response contract",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare Flask response contract."],
                "files_or_symbols": ["src/flask/app.py:make_response"],
                "first_slice": {"targets": ["src/flask/app.py:make_response"]},
            },
            "source_context": {
                "src/flask/app.py:make_response": {
                    "kind": "method",
                    "signature": {
                        "args": [
                            {"name": "self"},
                            {"name": "rv", "annotation": "ft.ResponseReturnValue"},
                        ],
                        "returns": "Response",
                    },
                    "snippet": {"text": "def make_response(self, rv): return self.response_class(rv)"},
                },
            },
        }
    )

    contract = spec["extraction_contract"]

    assert contract["input_contract"] == {"rv": "ft.ResponseReturnValue"}
    assert contract["semantic_contract"]["input_contract"]["return_value"].startswith("ViewReturnValue")


def test_technical_spec_uses_generalized_contract_archetype_without_exact_profile():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Prepare attrs class synthesis contract",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare generated class contract."],
                "files_or_symbols": ["src/attr/_make.py:_create_slots_class"],
                "first_slice": {"targets": ["src/attr/_make.py:_create_slots_class"]},
            },
            "source_context": {
                "src/attr/_make.py:_create_slots_class": {
                    "kind": "method",
                    "signature": {
                        "args": [
                            {"name": "cls"},
                            {"name": "attrs", "annotation": "list"},
                        ],
                        "returns": "type",
                    },
                    "snippet": {"text": "def _create_slots_class(cls, attrs):\n    return type(cls.__name__, (), {})"},
                },
            },
        }
    )

    contract = spec["extraction_contract"]

    assert contract["contract_family"] == "class_synthesis_factory"
    assert contract["semantic_contract"]["output_contract"]["generated_class"].startswith("GeneratedClass")
    assert contract["validation_gates"]


def test_technical_spec_infers_void_side_effect_contract_from_write_snippet():
    spec = build_technical_spec(
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "goal": "Prepare stored query writer contract",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare stored query contract."],
                "files_or_symbols": ["datasette/stored_queries.py:add_query"],
                "first_slice": {"targets": ["datasette/stored_queries.py:add_query"]},
            },
            "source_context": {
                "datasette/stored_queries.py:add_query": {
                    "kind": "pure_transform",
                    "signature": {
                        "args": [
                            {"name": "datasette"},
                            {"name": "database"},
                            {"name": "name"},
                            {"name": "sql"},
                        ],
                        "returns": "",
                    },
                    "snippet": {
                        "text": "async def add_query(datasette, database, name, sql):\n    await datasette.get_internal_database().execute_write('insert', [database, name, sql])"
                    },
                },
            },
        }
    )

    assert spec["extraction_contract"]["output_contract"] == {"result": "VoidSideEffect"}
