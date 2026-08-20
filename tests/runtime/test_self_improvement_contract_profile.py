from runtime.self_improvement_contract_profile import discover_contract_profile_candidates, synthesize_contract_profile


def test_synthesizes_external_sync_profile_from_source_evidence(tmp_path):
    source = tmp_path / "integration.py"
    source.write_text(
        "async def sync_records(client, db) -> dict[str, int]:\n"
        "    try:\n"
        "        rows = await client.fetch()\n"
        "        changed = 0\n"
        "        for row in rows:\n"
        "            changed += 1\n"
        "        await db.commit()\n"
        "        return {'changed': changed}\n"
        "    except RuntimeError:\n"
        "        raise\n",
        encoding="utf-8",
    )

    profile = synthesize_contract_profile(tmp_path, "integration.py:sync_records")

    assert profile["contract_family"] == "external_service_state_sync_boundary"
    assert profile["score_bonus"] == 0
    assert all(profile["training_evidence"].values())


def test_rejects_generic_function_without_integration_evidence(tmp_path):
    (tmp_path / "service.py").write_text("def sync_records(value):\n    return value\n", encoding="utf-8")

    assert synthesize_contract_profile(tmp_path, "service.py:sync_records") is None


def test_synthesizes_dynamic_dispatch_profile_from_source_evidence(tmp_path):
    (tmp_path / "domain.py").write_text(
        "class Domain:\n"
        "    def execute(self, method=None):\n"
        "        return getattr(self, method)(**self.request.get_values())\n",
        encoding="utf-8",
    )

    profile = synthesize_contract_profile(tmp_path, "domain.py:execute")

    assert profile["contract_family"] == "dynamic_method_dispatch_boundary"
    assert profile["input_contract"]["receiver_state"] == "DispatchReceiver(request_values, handlers)"
    assert all(profile["training_evidence"].values())


def test_synthesizes_external_api_command_profile_from_source_evidence(tmp_path):
    (tmp_path / "client.py").write_text(
        "class Client:\n"
        "    def send_message(self, user, body):\n"
        "        return self._post('/messages/{}'.format(user), {'message': str(body)})\n",
        encoding="utf-8",
    )

    profile = synthesize_contract_profile(tmp_path, "client.py:send_message")

    assert profile["contract_family"] == "external_api_command_boundary"
    assert profile["side_effect_policy"]["declared"] == ["network"]
    assert all(profile["training_evidence"].values())


def test_rejects_read_only_api_query_as_external_command(tmp_path):
    (tmp_path / "client.py").write_text(
        "class Client:\n"
        "    def matches(self, since):\n"
        "        return self._get('/matches', {'since': since})\n",
        encoding="utf-8",
    )

    assert synthesize_contract_profile(tmp_path, "client.py:matches") is None


def test_rejects_private_transport_wrapper_as_external_command(tmp_path):
    (tmp_path / "client.py").write_text(
        "class Client:\n"
        "    def _post(self, path, data):\n"
        "        return self._request('post', path, data=data)\n",
        encoding="utf-8",
    )

    assert synthesize_contract_profile(tmp_path, "client.py:_post") is None


def test_synthesizes_stateful_recursive_xml_serializer_profile(tmp_path):
    (tmp_path / "serializer.py").write_text(
        "class Serializer:\n"
        "    def serialize_model(self, modelObject, tagName='event', level=0):\n"
        "        if modelObject.type == 'human':\n            modelObject.type = normalize(modelObject.type)\n"
        "        xml = Element(tagName)\n"
        "        for name in modelObject.get_properties():\n"
        "            child = self.serialize_model(getattr(modelObject, name), name, level + 1)\n"
        "            xml.append(child)\n"
        "        return etree.tostring(xml) if level == 0 else xml\n",
        encoding="utf-8",
    )

    profile = synthesize_contract_profile(tmp_path, "serializer.py:serialize_model")

    assert profile["contract_family"] == "stateful_recursive_xml_serialization_boundary"
    assert all(profile["training_evidence"].values())


def test_rejects_unbounded_getattr_invocation(tmp_path):
    (tmp_path / "domain.py").write_text(
        "def execute(target, method):\n    return getattr(target, method)()\n",
        encoding="utf-8",
    )

    assert synthesize_contract_profile(tmp_path, "domain.py:execute") is None


def test_rejects_source_outside_project(tmp_path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("async def sync_records():\n    return {}\n", encoding="utf-8")

    assert synthesize_contract_profile(tmp_path, "../outside.py:sync_records") is None


def test_discovers_only_typed_profile_candidates(tmp_path):
    (tmp_path / "integration.py").write_text(
        "async def sync_records(client, db) -> dict[str, int]:\n"
        "    try:\n"
        "        rows = await client.fetch()\n"
        "        changed = len(rows)\n"
        "        await db.commit()\n"
        "        return {'changed': changed}\n"
        "    except RuntimeError:\n"
        "        raise\n\n"
        "def sync_fake(value):\n"
        "    return value\n",
        encoding="utf-8",
    )

    result = discover_contract_profile_candidates(tmp_path)

    assert [row["source"] for row in result] == ["integration.py:sync_records"]


def test_discovery_honors_file_limit(tmp_path):
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text(
            "async def sync_records(client, db) -> dict[str, int]:\n"
            "    try:\n"
            "        rows = await client.fetch()\n"
            "        await db.commit()\n"
            "        return {'changed': len(rows)}\n"
            "    except RuntimeError:\n"
            "        raise\n",
            encoding="utf-8",
        )

    assert len(discover_contract_profile_candidates(tmp_path, max_files=1)) == 1


def test_discovery_skips_excluded_dependency_trees(tmp_path):
    dependency = tmp_path / "node_modules"
    dependency.mkdir()
    (dependency / "integration.py").write_text(
        "async def sync_records(client, db) -> dict:\n"
        "    try:\n        rows = await client.fetch()\n        await db.commit()\n"
        "        return {'changed': len(rows)}\n    except RuntimeError:\n        raise\n",
        encoding="utf-8",
    )

    assert discover_contract_profile_candidates(tmp_path) == []
