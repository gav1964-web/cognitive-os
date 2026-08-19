from runtime.source_contract_semantics import infer_source_contract
from runtime.technical_spec_builder import _input_contract_from_candidate


def test_fstring_accumulator_proves_string_output():
    evidence = infer_source_contract(
        {"snippet": "def build(item):\n    result = f'value={item}'\n    result += '!'\n    return result"}
    )

    assert evidence["inferred_output_type"] == "str"


def test_sequence_translate_return_is_a_concrete_string():
    contract = infer_source_contract(
        {
            "signature": {"args": [{"name": "sequence", "annotation": "str"}], "returns": ""},
            "snippet": "def reverse_complement(sequence):\n    return sequence[::-1].translate(TABLE)\n",
        }
    )

    assert contract["inferred_output_type"] == "str"
    assert contract["output_inference_basis"] == "return_expression"


def test_len_return_is_a_concrete_integer():
    contract = infer_source_contract(
        {
            "signature": {"args": [{"name": "value", "annotation": ""}], "returns": ""},
            "snippet": "def byte_length(value):\n    return len(value.encode('utf-8'))\n",
        }
    )

    assert contract["inferred_output_type"] == "int"


def test_generic_docstring_object_falls_back_to_named_contract_type():
    contract = _input_contract_from_candidate(
        {
            "source": "equation.py:assemble",
            "signature": {"args": [{"name": "meanFlow", "annotation": ""}]},
            "snippet": "def assemble(meanFlow):\n    '''\n    meanFlow : object\n    '''\n    return 1\n",
        }
    )

    assert contract == {"meanFlow": "MeanFlowLike"}


def test_split_prefix_selection_returns_a_concrete_string():
    contract = infer_source_contract(
        {
            "signature": {
                "args": [{"name": "protein_id", "annotation": ""}, {"name": "known_ids", "annotation": ""}],
                "returns": "",
            },
            "snippet": (
                "def recover(protein_id, known_ids):\n"
                "    parts = protein_id.split('_')\n"
                "    for index in range(len(parts) - 1, 0, -1):\n"
                "        candidate = '_'.join(parts[:index])\n"
                "        if candidate in known_ids:\n"
                "            return candidate\n"
                "    return protein_id.rsplit('_', 1)[0]\n"
            ),
        }
    )

    assert contract["inferred_output_type"] == "str"


def test_formatted_argument_and_static_method_have_concrete_receiver_free_contract():
    candidate = {
        "source": "notify.py:format_message",
        "decorators": ["staticmethod"],
        "owner_class": "Notifier",
        "signature": {"args": [{"name": "message", "annotation": ""}]},
        "snippet": "@staticmethod\ndef format_message(message):\n    return f'Message: {message}'",
    }

    evidence = infer_source_contract(candidate)
    contract = _input_contract_from_candidate(candidate)

    assert evidence["argument_usage_types"]["message"] == "str"
    assert contract == {"message": "str"}


def test_nested_snippet_signature_remains_authoritative_for_contract_type():
    contract = _input_contract_from_candidate(
        {
            "source": "platform.py:normalize_machine",
            "snippet": {
                "text": "def normalize_machine(machine=None):\n    return (machine or default()).strip()",
                "signature": {
                    "args": [{"name": "machine", "annotation": "str | None"}],
                    "returns": "str",
                },
            },
            "structural_contract": {
                "argument_usage_types": {"machine": "bool"},
                "argument_constraint_types": {"machine": "NoneType"},
            },
        }
    )

    assert contract == {"machine": "str | None"}
