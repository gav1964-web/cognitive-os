from runtime.contract_archetype_inference import contract_archetype_for_target


def test_proxy_loop_has_bounded_flow_orchestration_contract():
    contract = contract_archetype_for_target("decept.py:proxy_loop")

    assert contract["contract_family"] == "proxy_flow_orchestration_boundary"
    assert "flow_input" in contract["input_contract"]
    assert contract["output_contract"]["operation"] == "VoidSideEffect"


def test_unrelated_event_loop_does_not_match_proxy_contract():
    assert contract_archetype_for_target("runtime/events.py:event_loop").get("contract_family") != (
        "proxy_flow_orchestration_boundary"
    )
