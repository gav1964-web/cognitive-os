from runtime.self_improvement_contract_profile import synthesize_contract_profile


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


def test_rejects_source_outside_project(tmp_path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("async def sync_records():\n    return {}\n", encoding="utf-8")

    assert synthesize_contract_profile(tmp_path, "../outside.py:sync_records") is None
