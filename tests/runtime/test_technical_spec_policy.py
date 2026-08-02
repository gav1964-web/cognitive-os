from __future__ import annotations

from runtime._parts.technical_spec_builder_part3 import _input_contract_from_signature
from runtime.technical_spec_builder import build_technical_spec
from runtime.technical_spec_policy import load_technical_spec_policy


def test_technical_spec_policy_loads_required_sections():
    policy = load_technical_spec_policy()

    assert policy["schema_version"] == "technical_spec_policy.v1"
    assert policy["context_only_source_path_tokens"]
    assert policy["snippet_analysis"]["allowed_external_names"]
    assert policy["contract_type_inference"]["argument_rules"]
    assert policy["semantic_rerank"]["scan_limit"] >= 2


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
