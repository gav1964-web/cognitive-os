import json
import sys

import pytest

from runtime.integrity import hash_plugin_dir
from runtime.plugin_lint import PluginLintError, lint_plugin


def setup_package(tmp_path, monkeypatch):
    package = tmp_path / "fixture_implementation"
    package.mkdir()
    (package / "__init__.py").write_text("raise RuntimeError('must not import during metadata checks')\n", encoding="utf-8")
    source = package / "logic.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "plugin.json").write_text(json.dumps({"implementation_packages": [package.name]}), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return plugin, source


def test_package_source_changes_affect_plugin_hash_without_import(tmp_path, monkeypatch):
    plugin, source = setup_package(tmp_path, monkeypatch)
    before = hash_plugin_dir(plugin)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert hash_plugin_dir(plugin) != before
    assert "fixture_implementation" not in sys.modules


def test_implementation_is_linted_for_declared_effects(tmp_path, monkeypatch):
    plugin, source = setup_package(tmp_path, monkeypatch)
    source.write_text("import requests\n", encoding="utf-8")
    with pytest.raises(PluginLintError, match="network"):
        lint_plugin(plugin, "fixture")


def test_missing_implementation_fails_closed(tmp_path):
    (tmp_path / "plugin.json").write_text('{"implementation_packages":["unavailable_cos_fixture_package"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="not installed"):
        hash_plugin_dir(tmp_path)
