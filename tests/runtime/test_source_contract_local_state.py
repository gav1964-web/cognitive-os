from runtime.source_contract_semantics import infer_source_contract


def test_local_object_attribute_updates_are_not_external_state_mutation():
    local = infer_source_contract(
        {"snippet": "def build():\n    result = Result()\n    result.value = 1\n    return result"}
    )
    receiver = infer_source_contract(
        {"snippet": "def update(self):\n    self.value = 1"}
    )

    assert local["state_mutation"] is False
    assert receiver["state_mutation"] is True
