from __future__ import annotations

from pathlib import Path
from typing import Any


def _primary_language_scope(path: Path) -> dict[str, Any]:
    top_files = {child.name.lower() for child in path.iterdir() if child.is_file()}
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    py_files = list(path.rglob("*.py"))
    rust_files = list(path.rglob("*.rs"))
    c_files = [*path.rglob("*.c"), *path.rglob("*.h")]
    cpp_files = [*path.rglob("*.cc"), *path.rglob("*.cpp"), *path.rglob("*.cxx"), *path.rglob("*.hpp")]
    native_files = [*rust_files, *c_files, *cpp_files]
    python_source_files = [file for file in py_files if _python_role_source_file(file.relative_to(path))]
    root_package = _root_python_package(path)
    has_root_python_source = bool(root_package or (path / "src").is_dir() or (path / "app").is_dir())
    c_runtime_core = (
        len(c_files) >= 100
        and not root_package
        and {"include", "modules"}.issubset(top_dirs)
        and bool({"objects", "python"}.intersection(top_dirs))
    )
    cpp_runtime_core = len(cpp_files) >= 20 and not root_package and "src" in top_dirs
    native_core_without_python_impl = (
        "cargo.toml" in top_files
        and rust_files
        and not root_package
        and len(python_source_files) <= 2
        and len(rust_files) >= max(20, len(python_source_files) * 8)
    )
    rust_workspace = "cargo.toml" in top_files and ("crates" in top_dirs or len(rust_files) >= max(20, len(py_files) * 2))
    rust_dominates = len(rust_files) >= max(50, len(py_files) * 5)
    python_is_embedded = not has_root_python_source and (
        len(python_source_files) < max(8, len(py_files) // 2)
        or rust_dominates
    )
    if (rust_workspace and python_is_embedded) or native_core_without_python_impl:
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_primary_language_for_python_foundation",
            "primary_language": "Rust",
            "python_files": len(py_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "c_files": len(c_files),
            "evidence": {
                "top_level_cargo": "cargo.toml" in top_files,
                "crates_dir": "crates" in top_dirs,
                "root_python_package": root_package,
            },
        }
    if c_runtime_core:
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_primary_language_for_python_foundation",
            "primary_language": "C",
            "python_files": len(py_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "c_files": len(c_files),
            "cpp_files": len(cpp_files),
            "evidence": {
                "c_runtime_core_dirs": sorted(top_dirs.intersection({"include", "modules", "objects", "python"})),
                "root_python_package": root_package,
            },
        }
    if cpp_runtime_core:
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_primary_language_for_python_foundation",
            "primary_language": "C++",
            "python_files": len(py_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "c_files": len(c_files),
            "cpp_files": len(cpp_files),
            "evidence": {
                "native_source_files": len(native_files),
                "root_python_package": root_package,
                "src_dir": "src" in top_dirs,
            },
        }
    return {
        "status": "in_scope",
        "primary_language": "Python",
        "python_files": len(py_files),
        "python_source_files": len(python_source_files),
        "rust_files": len(rust_files),
        "c_files": len(c_files),
        "cpp_files": len(cpp_files),
        "evidence": {"root_python_package": root_package},
    }


def _child_python_projects(path: Path) -> list[Path]:
    return [child.resolve() for child in sorted(path.iterdir()) if child.is_dir() and _is_python_project(child)]


def _is_python_project(path: Path) -> bool:
    if not path.is_dir():
        return False
    if _has_project_manifest(path):
        return True
    if any(path.glob("*.py")):
        return True
    children = [child for child in path.iterdir() if child.is_dir()]
    if any(child.name in {"src", "app", "tests"} and any(child.rglob("*.py")) for child in children):
        return True
    py_files = list(path.rglob("*.py"))
    if len(py_files) >= 20 and any(_python_source_like(rel.relative_to(path)) for rel in py_files[:200]):
        return True
    return False


def _has_project_manifest(path: Path) -> bool:
    return any((path / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"))


def _python_role_source_file(path: Path) -> bool:
    normalized = path.as_posix().lower()
    excluded = {"tests", "test", "docs", "examples", "example", "scripts", ".github", "ci", "templates"}
    excluded.update({"bench", "benchmark", "benchmarks", "integration"})
    if any(part in excluded for part in normalized.split("/")):
        return False
    if "test" in path.name.lower() or path.name.lower().endswith("_template.py"):
        return False
    return True


def _root_python_package(path: Path) -> str | None:
    excluded = {"tests", "test", "docs", "examples", "scripts", "crates", "bench", "benchmark", "benchmarks", "integration"}
    for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir() or child.name.startswith(".") or child.name.lower() in excluded:
            continue
        if (child / "__init__.py").exists():
            return child.name
    return None


def _python_source_like(path: Path) -> bool:
    normalized = path.as_posix().lower()
    if any(token in normalized for token in ("/.git/", "/docs/", "/assets/", "/ci/", "/scripts/")):
        return False
    return "__init__.py" in normalized or "/src/" in normalized or normalized.count("/") >= 1
