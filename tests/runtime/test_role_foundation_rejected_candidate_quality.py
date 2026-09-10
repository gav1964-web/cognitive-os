from runtime._parts.role_foundation_pipeline_part1 import _selected_candidate_quality


def test_rejected_candidate_keeps_original_semantic_evidence():
    quality = {
        "target": "helpers.py:Record.has_value",
        "score": 69,
        "status": "suspicious",
        "structural_evidence": {"return_paths": 1, "owner_class": "Record"},
    }
    spec = {"extraction_contract": {
        "candidate": None,
        "semantic_quality": quality,
        "structural_evidence": {},
    }}

    assert _selected_candidate_quality(spec) == quality
