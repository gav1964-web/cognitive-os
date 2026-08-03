from __future__ import annotations

from runtime.contract_archetype_inference import (
    archetype_score_adjustments,
    contract_archetype_for_target,
    matching_archetypes,
)
from runtime.target_quality import semantic_target_quality_report


def test_contract_archetype_inference_matches_generalized_holdout_shapes():
    cases = {
        "src/attr/_make.py:_create_slots_class": "class_synthesis_factory",
        "src/urllib3/connectionpool.py:urlopen": "protocol_request_transaction",
        "more_itertools/more.py:distinct_permutations": "combinatorial_iterator_generation",
        "src/itsdangerous/url_safe.py:load_payload": "payload_serializer_loader",
        "src/jinja2/compiler.py:visit_For": "compiler_ast_visitor",
        "src/iniconfig/_parse.py:_parseline": "configuration_line_parser",
        "jsonschema/validators.py:create": "validator_factory",
        "starlette/authentication.py:requires": "permission_gate_decorator",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert matching_archetypes(target)[0]["id"] == archetype
        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_target_quality_uses_contract_archetype_as_generalized_family():
    report = semantic_target_quality_report(
        "src/urllib3/connectionpool.py:urlopen",
        ranked_candidates=["src/urllib3/connectionpool.py:urlopen"],
        source_evidence=["src/urllib3/connectionpool.py:urlopen"],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert report["profiled_contract_family"] is True
    assert report["contract_archetype_ids"] == ["protocol_request_transaction"]
