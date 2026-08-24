from runtime.self_improvement_engine_fingerprint import improvement_engine_fingerprint


def test_engine_fingerprint_changes_with_plugin_content(tmp_path):
    plugin = tmp_path / "runtime" / "improvement_plugins" / "example.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text("VALUE = 1\n", encoding="utf-8")
    before = improvement_engine_fingerprint(tmp_path)

    plugin.write_text("VALUE = 2\n", encoding="utf-8")

    assert improvement_engine_fingerprint(tmp_path) != before
