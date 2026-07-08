"""Static plugin lint gates for architectural invariants."""

from __future__ import annotations

import ast
from pathlib import Path


class PluginLintError(RuntimeError):
    """Raised when a plugin violates static architecture rules."""


def lint_plugin(
    plugin_dir: Path,
    plugin_id: str,
    *,
    side_effects: dict[str, str] | None = None,
    max_python_lines: int = 400,
) -> None:
    effects = side_effects or {"filesystem": "none", "network": "none", "secrets": "none"}
    for path in plugin_dir.rglob("*.py"):
        line_count = _line_count(path)
        if line_count > max_python_lines:
            rel_path = path.relative_to(plugin_dir).as_posix()
            raise PluginLintError(f"{plugin_id} file exceeds {max_python_lines} lines: {rel_path}:{line_count}")
        if "src" in path.relative_to(plugin_dir).parts:
            _lint_src_file(path, plugin_id, effects)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _reject_plugin_to_plugin_imports(path: Path, plugin_id: str) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    own_prefix = f"plugins.{plugin_id}."
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import(alias.name, own_prefix, path)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _check_import(node.module, own_prefix, path)


def _lint_src_file(path: Path, plugin_id: str, side_effects: dict[str, str]) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    own_prefix = f"plugins.{plugin_id}."
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import(alias.name, own_prefix, path)
                _check_side_effect_import(alias.name, side_effects, path)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _check_import(node.module, own_prefix, path)
            _check_side_effect_import(node.module, side_effects, path)
        elif isinstance(node, ast.Call):
            _check_side_effect_call(node, side_effects, path)


def _check_import(module_name: str, own_prefix: str, path: Path) -> None:
    if module_name == "plugins" or module_name.startswith("plugins."):
        if not module_name.startswith(own_prefix):
            raise PluginLintError(f"plugin-to-plugin import is forbidden in {path}: {module_name}")


def _check_side_effect_import(module_name: str, side_effects: dict[str, str], path: Path) -> None:
    filesystem = side_effects.get("filesystem", "none")
    network = side_effects.get("network", "none")
    secrets = side_effects.get("secrets", "none")
    if filesystem == "none" and module_name in {"pathlib", "shutil"}:
        raise PluginLintError(f"filesystem import requires declared filesystem side effect in {path}: {module_name}")
    if network == "none" and (
        module_name in {"socket", "requests"} or module_name.startswith("urllib")
    ):
        raise PluginLintError(f"network import requires declared network side effect in {path}: {module_name}")
    if secrets == "none" and module_name == "keyring":
        raise PluginLintError(f"secret access import requires declared secrets side effect in {path}: {module_name}")


def _check_side_effect_call(node: ast.Call, side_effects: dict[str, str], path: Path) -> None:
    filesystem = side_effects.get("filesystem", "none")
    if filesystem == "none" and isinstance(node.func, ast.Name) and node.func.id == "open":
        raise PluginLintError(f"open() requires declared filesystem side effect in {path}")
