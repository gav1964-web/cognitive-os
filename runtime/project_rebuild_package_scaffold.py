"""Package-shaped files for tooling/library rebuild scaffolds."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


RESERVED_FILES = {"app.py", "tests/test_contract.py"}


def build_package_entrypoint_files(spec: dict[str, Any]) -> dict[str, str]:
    """Create importable files that preserve source public entrypoints."""

    files: dict[str, str] = {}
    purpose = str(spec.get("main_task") or "Generated project entrypoint.")
    capabilities = [str(item) for item in list(spec.get("core_capabilities") or [])[:12]]
    public_shapes = _public_shapes(spec)
    for entrypoint in list(spec.get("entrypoints") or [])[:40]:
        path = _safe_python_path(str(entrypoint or ""))
        if not path or path in RESERVED_FILES:
            continue
        files[path] = _entrypoint_source(path, purpose, capabilities, public_shapes.get(path, {}))
        for parent_path, source in _parent_packages(path, purpose).items():
            files.setdefault(parent_path, source)
    return files


def _safe_python_path(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    if raw.startswith(("/", ".")):
        return ""
    cleaned = raw.strip("/")
    if not cleaned or cleaned.startswith((".", "/")):
        return ""
    path = PurePosixPath(cleaned)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        return ""
    if any(part in {"", ".", "__pycache__"} for part in path.parts):
        return ""
    return path.as_posix()


def _entrypoint_source(path: str, purpose: str, capabilities: list[str], public_shape: dict[str, str]) -> str:
    module_name = path[:-3].replace("/", ".")
    exports = list(public_shape) or ["describe_entrypoint"]
    return (
        f'"""Rebuilt public entrypoint for {module_name}.\n\n'
        f"Purpose: {purpose}\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        f"__all__ = {exports!r}\n"
        f"CAPABILITIES = {capabilities!r}\n\n"
        "def describe_entrypoint() -> dict:\n"
        f"    return {{'module': {module_name!r}, 'purpose': {purpose!r}, 'capabilities': CAPABILITIES}}\n"
        f"{_export_definitions(exports, public_shape)}"
    )


def _public_shapes(spec: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in list(spec.get("behavior_blueprints") or []):
        if not isinstance(row, dict) or row.get("kind") != "module_import":
            continue
        shape = dict(row.get("shape") or {})
        names = [str(item) for item in list(shape.get("public_names") or [])[:20] if _is_identifier(str(item))]
        kinds = dict(shape.get("attr_kinds") or {})
        if names:
            result[str(row.get("path") or "")] = {name: str(kinds.get(name) or "") for name in names}
    return result


def _export_definitions(exports: list[str], public_shape: dict[str, str]) -> str:
    lines = []
    for name in exports:
        if name == "describe_entrypoint":
            continue
        kind = public_shape.get(name)
        if name == "__version__":
            lines.append(f"{name} = '0.0.0'")
        elif name == "VERSION":
            lines.append(f"{name} = (0, 0, 0)")
        elif kind in {"type", "ABCMeta"} or name[:1].isupper():
            lines.append(f"class {name}:")
            lines.append("    pass")
        elif kind == "function" or name.isidentifier():
            lines.append(f"def {name}(*args, **kwargs):")
            lines.append("    return describe_entrypoint()")
    return ("\n\n" + "\n".join(lines) + "\n") if lines else ""


def _parent_packages(path: str, purpose: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pure_path = PurePosixPath(path)
    if pure_path.name == "__init__.py":
        return result
    parts = pure_path.parts[:-1]
    start = _package_root_index(parts)
    for index in range(start + 1, len(parts) + 1):
        if not all(_is_identifier(part) for part in parts[start:index]):
            continue
        init_path = PurePosixPath(*parts[:index], "__init__.py").as_posix()
        if init_path == path:
            continue
        package_name = ".".join(parts[start:index])
        result[init_path] = (
            f'"""Rebuilt package marker for {package_name}.\n\n'
            f"Purpose: {purpose}\n"
            '"""\n'
        )
    return result


def _package_root_index(parts: tuple[str, ...]) -> int:
    for marker in ("src", "lib"):
        if marker in parts[:-1]:
            return parts.index(marker) + 1
    return 0


def _is_identifier(value: str) -> bool:
    return value.replace("_", "").isalnum() and not value[0].isdigit()
