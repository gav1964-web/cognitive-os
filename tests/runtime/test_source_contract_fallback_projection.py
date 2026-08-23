from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report


def test_protocol_string_fallback_projection_is_recognized_from_ast():
    target = "domain/helpers.py:resolve_label"
    structural = infer_source_contract({
        "signature": {
            "args": [{"name": "record", "annotation": "Record"}],
            "returns": "str",
        },
        "snippet": (
            "def resolve_label(record: Record) -> str:\n"
            "    try:\n"
            "        return record.primary.label\n"
            "    except AttributeError:\n"
            "        return record.name"
        ),
    })

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence=structural,
        input_contract={"record": "Record"},
        output_contract={"result": "str"},
        side_effect_contract={"declared": []},
    )

    assert report["status"] == "strong"
    assert "protocol_string_fallback_projection" in report["contract_archetype_ids"]
    assert "support/utility target" not in " ".join(report["reasons"])
