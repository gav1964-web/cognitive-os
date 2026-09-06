"""Distribution and source entrypoint evidence for Project Map."""

from __future__ import annotations

from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 runtime
    import tomli as tomllib

from .core_paths import is_core_path


PLUGIN_GROUPS = {
    "babel.extractors",
    "flake8.extension",
    "flake8.report",
    "hatch",
    "mkdocs.plugins",
    "mypy.plugins",
    "pytest11",
    "sphinx.html_themes",
    "tox",
}


def declared_script_entrypoints(files: dict[str, Any]) -> list[str]:
    payload = _pyproject_payload(files)
    if not payload:
        return []
    scripts = dict(dict(payload.get("project") or {}).get("scripts") or {})
    poetry = dict(dict(dict(payload.get("tool") or {}).get("poetry") or {}).get("scripts") or {})
    return [
        f"pyproject.toml:[project.scripts]:{name}={target}"
        for name, target in sorted({**poetry, **scripts}.items())
        if isinstance(target, str) and target.strip()
    ][:40]


def declared_plugin_entrypoints(files: dict[str, Any]) -> list[str]:
    payload = _pyproject_payload(files)
    if not payload:
        return []
    project = dict(dict(payload.get("project") or {}).get("entry-points") or {})
    poetry = dict(dict(dict(payload.get("tool") or {}).get("poetry") or {}).get("plugins") or {})
    declared = {**poetry, **project}
    entries = []
    for group, values in sorted(declared.items()):
        if str(group) not in PLUGIN_GROUPS or not isinstance(values, dict):
            continue
        entries.extend(
            f"pyproject.toml:[plugin:{group}]:{name}={target}"
            for name, target in sorted(values.items())
            if isinstance(target, str) and target.strip()
        )
    return entries[:40]


def _pyproject_payload(files: dict[str, Any]) -> dict[str, Any]:
    row = next(
        (
            dict(item)
            for item in files.get("files", [])
            if isinstance(item, dict) and item.get("path") == "pyproject.toml"
        ),
        None,
    )
    if not row or not isinstance(row.get("text"), str):
        return {}
    try:
        payload = tomllib.loads(str(row["text"]))
    except (tomllib.TOMLDecodeError, ValueError):
        return {}
    return payload


def project_entrypoints(
    stack: dict[str, Any], python_structure: dict[str, Any]
) -> list[str]:
    declared = [str(item) for item in stack.get("declared_script_entrypoints", []) if item]
    stack_entrypoints = [
        str(item)
        for item in stack.get("entrypoints", [])
        if item and (str(item) in declared or is_core_path(str(item)))
    ]
    package_inits = _package_init_entrypoints(python_structure)
    if stack_entrypoints:
        return sorted(dict.fromkeys([*stack_entrypoints, *package_inits]))[:40]
    if package_inits:
        return package_inits[:40]
    return _top_level_module_entrypoints(python_structure)[:8]


def _package_init_entrypoints(python_structure: dict[str, Any]) -> list[str]:
    package_inits = []
    for file_row in python_structure.get("files", []):
        path = str(file_row.get("path") or "")
        if not path.endswith("/__init__.py") or not is_core_path(path):
            continue
        parts = path.split("/")
        if parts[0] in {"src", "lib"} and len(parts) >= 3:
            package_inits.append(path)
        elif "src" in parts[:-2]:
            src_index = parts.index("src")
            if len(parts) - src_index >= 3:
                package_inits.append(path)
        elif len(parts) == 2 and parts[0].replace("_", "").isalnum():
            package_inits.append(path)
    return sorted(package_inits)


def _top_level_module_entrypoints(python_structure: dict[str, Any]) -> list[str]:
    modules = []
    for file_row in python_structure.get("files", []):
        path = str(file_row.get("path") or "").replace("\\", "/")
        if "/" in path or not path.endswith(".py") or path == "__init__.py":
            continue
        if is_core_path(path):
            modules.append(path)
    return sorted(dict.fromkeys(modules))
