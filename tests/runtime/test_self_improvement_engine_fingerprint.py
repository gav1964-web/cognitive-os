from runtime.self_improvement_engine_fingerprint import improvement_engine_fingerprint


def test_engine_fingerprint_changes_with_plugin_content(tmp_path):
    plugin = tmp_path / "runtime" / "improvement_plugins" / "example.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text("VALUE = 1\n", encoding="utf-8")
    before = improvement_engine_fingerprint(tmp_path)

    plugin.write_text("VALUE = 2\n", encoding="utf-8")

    assert improvement_engine_fingerprint(tmp_path) != before


def test_engine_fingerprint_changes_with_hypothesis_compiler_policy(tmp_path):
    policy = tmp_path / "config" / "hypothesis_compiler.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"minimum_cluster_projects":3}\n', encoding="utf-8")
    before = improvement_engine_fingerprint(tmp_path)

    policy.write_text('{"minimum_cluster_projects":4}\n', encoding="utf-8")

    assert improvement_engine_fingerprint(tmp_path) != before


def test_engine_fingerprint_changes_with_project_archetype_knowledge(tmp_path):
    knowledge = tmp_path / "knowledge" / "architecture_patterns" / "project_archetypes.json"
    knowledge.parent.mkdir(parents=True)
    knowledge.write_text('{"records":[]}\n', encoding="utf-8")
    before = improvement_engine_fingerprint(tmp_path)

    knowledge.write_text('{"records":[{"rule_id":"owned_backend"}]}\n', encoding="utf-8")

    assert improvement_engine_fingerprint(tmp_path) != before
