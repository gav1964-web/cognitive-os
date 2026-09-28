from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report


def test_constant_return_hook_is_not_a_strong_first_slice():
    target = "admin.py:EntryAdmin.has_add_permission"
    structural = infer_source_contract({
        "signature": {
            "args": [
                {"name": "self", "annotation": ""},
                {"name": "request", "annotation": ""},
            ],
        },
        "snippet": "def has_add_permission(self, request):\n    return False",
    })

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence=structural,
        input_contract={"request": "RequestLike"},
        output_contract={"result": "bool"},
        side_effect_contract={"declared": []},
    )

    assert structural["literal_return_only"] is True
    assert report["score"] <= 69
    assert report["status"] == "suspicious"
    assert "constant-return hook is weak as first architectural slice" in report["reasons"]


def test_nonconstant_hook_keeps_structural_distinction():
    structural = infer_source_contract({
        "signature": {"args": [{"name": "value", "annotation": "bool"}]},
        "snippet": "def has_value(value: bool) -> bool:\n    return bool(value)",
    })

    assert structural["literal_return_only"] is False
