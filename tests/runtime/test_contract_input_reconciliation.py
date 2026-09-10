from runtime.contract_input_reconciliation import reconcile_input_contract


def test_binds_unit_of_work_and_remaining_record_fields():
    contract = reconcile_input_contract(
        {"session": "ProtocolLike", "graph_id": "Identifier", "value": "InferredValue"},
        {"unit_of_work": "PersistenceSession(add)", "record_data": "RecordAppendInput(values)"},
        {"unit_of_work": ["session", "db", "unit_of_work", "uow"], "record_data": ["*remaining"]},
    )

    assert contract == {
        "unit_of_work": "PersistenceSession(add)",
        "record_data": "RecordAppendInput(values)",
    }


def test_incomplete_binding_preserves_source_signature():
    signature = {"client": "ProtocolLike", "payload": "MappingLike", "timeout": "int"}

    contract = reconcile_input_contract(
        signature,
        {"request": "ExternalRequest", "dependencies": "ExternalDependencies"},
        {"dependencies": ["client"]},
    )

    assert contract == signature


def test_concrete_source_annotation_wins_over_single_field_domain_guess():
    contract = reconcile_input_contract(
        {"machine": "str | None"},
        {"value": "bool"},
    )

    assert contract == {"machine": "str | None"}
