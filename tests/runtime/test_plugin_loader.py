from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from runtime.plugin_loader import PluginLoadError, load_capabilities


def test_loader_rejects_plugin_id_that_differs_from_directory(tmp_path):
    root = tmp_path
    source = Path(__file__).resolve().parents[2] / "plugins" / "fetch_html"
    target = root / "plugins" / "renamed_plugin"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (root / "plugins" / "__init__.py").write_text('"""test plugins."""\n', encoding="utf-8")

    with pytest.raises(PluginLoadError, match="match directory"):
        load_capabilities(root)


def test_loader_rejects_missing_fallback_target(tmp_path):
    root = tmp_path
    source = Path(__file__).resolve().parents[2] / "plugins" / "parse_title_fallback"
    target = root / "plugins" / "parse_title_fallback"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (root / "plugins" / "__init__.py").write_text('"""test plugins."""\n', encoding="utf-8")
    manifest_path = target / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fallback_for"] = ["missing_plugin"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PluginLoadError, match="fallback target"):
        load_capabilities(root)


def test_loader_rejects_schema_without_additional_properties_false(tmp_path):
    root = tmp_path
    source = Path(__file__).resolve().parents[2] / "plugins" / "fetch_html"
    target = root / "plugins" / "fetch_html"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (root / "plugins" / "__init__.py").write_text('"""test plugins."""\n', encoding="utf-8")
    schema_path = target / "schemas" / "input.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema.pop("additionalProperties")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(PluginLoadError, match="additionalProperties=false"):
        load_capabilities(root)


def test_loader_rejects_entrypoint_with_wrong_signature(tmp_path):
    root = tmp_path
    source = Path(__file__).resolve().parents[2] / "plugins" / "fetch_html"
    target = root / "plugins" / "fetch_html"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (root / "plugins" / "__init__.py").write_text('"""test plugins."""\n', encoding="utf-8")
    (target / "src" / "main.py").write_text(
        "def run(payload, extra):\n    return {\"html\": \"x\"}\n",
        encoding="utf-8",
    )
    capabilities = load_capabilities(root)

    from runtime.plugin_loader import load_entrypoint

    sys.path = [str(root)] + [item for item in sys.path if item != str(root)]
    for name in list(sys.modules):
        if name == "plugins" or name.startswith("plugins."):
            sys.modules.pop(name, None)
    with pytest.raises(TypeError, match="exactly one"):
        load_entrypoint(capabilities["fetch_html"].entrypoint)
