from plugins.project_map_report.src.runtime_readiness import minimal_extraction_plan
from plugins.project_map_report.src.runtime_readiness_helpers import unsafe_candidate_reason


def test_protocol_dunder_methods_are_not_safe_standalone_extraction_targets():
    for name in ("__eq__", "__repr__", "__ne__", "__aexit__"):
        assert unsafe_candidate_reason({"path": "pkg/model.py", "name": name}) == "protocol_dunder_method"


def test_minimal_extraction_plan_prefers_public_transform_over_dunder_anchor():
    dunder = {"path": "pkg/model.py", "name": "__eq__", "loc": 80, "call_count": 20, "side_effects": []}
    public = {"path": "pkg/model.py", "name": "to_dict", "loc": 25, "call_count": 4, "side_effects": []}
    plan = minimal_extraction_plan(
        {
            "domain_flow_anchors": [dunder],
            "central_nodes": [dunder],
            "pure_transform_candidates": [dunder, public],
        },
        [],
        [],
        domain_profile={"target_markers": ["eq"]},
    )

    capabilities = [row["capability"] for row in plan["capabilities_to_extract"]]
    assert capabilities == ["pkg/model.py:to_dict"]
