import ast

from runtime.self_improvement_profile_families import load_contract_families, recognize_contract_family


def _recognize(source: str):
    node = ast.parse(source).body[0]
    return recognize_contract_family(node)


def test_contract_family_catalog_loads_typed_templates():
    payload = load_contract_families()

    assert payload["schema_version"] == "self_improvement_contract_families.v1"
    assert set(payload["families"]) >= {
        "external_service_state_sync_boundary",
        "file_extension_admission_policy",
        "route_tree_flatten_boundary",
        "persistence_append_command",
    }


def test_recognizes_file_extension_admission_policy():
    result = _recognize(
        "def allowed_file(filename):\n"
        "    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS\n"
    )

    assert result[0] == "file_extension_admission_policy"
    assert all(result[1].values())


def test_recognizes_route_tree_flatten_boundary():
    result = _recognize(
        "def flatten(routes):\n"
        "    if iter_route_contexts is not None:\n"
        "        for route in iter_route_contexts(routes):\n"
        "            yield matchable_route(route)\n"
        "        return\n"
        "    for starlette_route in routes:\n"
        "        yield starlette_route\n"
    )

    assert result[0] == "route_tree_flatten_boundary"


def test_recognizes_persistence_append_command():
    result = _recognize(
        "def add_value(session, graph_id, value):\n"
        "    record = GraphData(graph_id=graph_id, value=value)\n"
        "    session.add(record)\n"
    )

    assert result[0] == "persistence_append_command"


def test_rejects_similarly_named_helpers_without_complete_evidence():
    assert _recognize("def allowed_file(filename):\n    return bool(filename)\n") is None
    assert _recognize("def flatten(routes):\n    return list(routes)\n") is None
    assert _recognize("def add_value(values, value):\n    values.append(value)\n") is None
