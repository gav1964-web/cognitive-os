from __future__ import annotations

from pathlib import Path

import pytest

from runtime.plugin_lint import PluginLintError, lint_plugin


def test_lint_rejects_python_file_over_400_lines(tmp_path):
    plugin = tmp_path / "plugins" / "too_big"
    src = plugin / "src"
    src.mkdir(parents=True)
    (src / "main.py").write_text("\n".join(["x = 1"] * 401), encoding="utf-8")

    with pytest.raises(PluginLintError, match="exceeds 400"):
        lint_plugin(plugin, "too_big")


def test_lint_rejects_plugin_to_plugin_import(tmp_path):
    plugin = tmp_path / "plugins" / "alpha"
    src = plugin / "src"
    src.mkdir(parents=True)
    (src / "main.py").write_text("import plugins.beta.src.main\n", encoding="utf-8")

    with pytest.raises(PluginLintError, match="plugin-to-plugin"):
        lint_plugin(plugin, "alpha")

