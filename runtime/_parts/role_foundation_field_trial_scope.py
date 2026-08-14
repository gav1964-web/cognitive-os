from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _primary_language_scope(path: Path) -> dict[str, Any]:
    top_files = {child.name.lower() for child in path.iterdir() if child.is_file()}
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    py_files = _files_with_suffixes(path, {".py"})
    pyi_files = _files_with_suffixes(path, {".pyi"})
    rust_files = _files_with_suffixes(path, {".rs"})
    c_files = _files_with_suffixes(path, {".c", ".h"})
    cpp_files = _files_with_suffixes(path, {".cc", ".cpp", ".cxx", ".hpp"})
    cython_files = _files_with_suffixes(path, {".pyx", ".pxd"})
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
    native_extension_wrapper = _native_extension_wrapper_without_python_core(python_source_files, rust_files)
    cpp_extension_wrapper = _cpp_extension_wrapper_without_python_core(top_files, root_package, python_source_files, cpp_files)
    cython_extension_wrapper = _cython_extension_wrapper_without_python_core(
        top_files, root_package, python_source_files, cython_files
    )
    rust_workspace = "cargo.toml" in top_files and ("crates" in top_dirs or len(rust_files) >= max(20, len(py_files) * 2))
    rust_dominates = len(rust_files) >= max(50, len(py_files) * 5)
    python_is_embedded = not has_root_python_source and (
        len(python_source_files) < max(8, len(py_files) // 2)
        or rust_dominates
    )
    if (rust_workspace and python_is_embedded) or native_core_without_python_impl or native_extension_wrapper:
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_primary_language_for_python_foundation",
            "primary_language": "Rust native extension",
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
    if cpp_extension_wrapper or cython_extension_wrapper:
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_primary_language_for_python_foundation",
            "primary_language": "Cython native extension" if cython_extension_wrapper else "C++ native extension",
            "python_files": len(py_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "c_files": len(c_files),
            "cpp_files": len(cpp_files),
            "evidence": {
                "native_source_files": len(native_files),
                "cython_source_files": len(cython_files),
                "root_python_package": root_package,
                "extension_manifest": sorted(top_files.intersection({"setup.py", "pyproject.toml"})),
            },
        }
    if _type_stub_corpus(top_dirs, py_files, pyi_files):
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_type_stub_corpus_for_python_foundation",
            "primary_language": "Python type stubs",
            "python_files": len(py_files),
            "python_stub_files": len(pyi_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "c_files": len(c_files),
            "cpp_files": len(cpp_files),
            "evidence": {
                "stub_dirs": sorted(top_dirs.intersection({"stdlib", "stubs"})),
                "root_python_package": root_package,
            },
        }
    no_owned_boundary = (
        not py_files
        or _examples_only_python_corpus(path, py_files, python_source_files)
        or _independent_project_collection(path)
        or _documentation_led_demo(path, python_source_files, root_package)
        or _documentation_code_examples(path, python_source_files, root_package)
        or _documentation_index_with_fetch_script(path, python_source_files, root_package)
    )
    if no_owned_boundary:
        return {
            "status": "out_of_scope",
            "reason_code": "no_python_owned_product_boundary",
            "primary_language": "No Python product implementation",
            "python_files": len(py_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "c_files": len(c_files),
            "cpp_files": len(cpp_files),
            "evidence": {"top_dirs": sorted(top_dirs), "root_python_package": root_package},
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


def _type_stub_corpus(top_dirs: set[str], py_files: list[Path], pyi_files: list[Path]) -> bool:
    if not {"stdlib", "stubs"}.issubset(top_dirs):
        return False
    return len(pyi_files) >= max(200, len(py_files) * 10)


def _examples_only_python_corpus(path: Path, py_files: list[Path], python_source_files: list[Path]) -> bool:
    if len(python_source_files) == 1 and " " in python_source_files[0].name and not _has_project_manifest(path):
        return True
    if python_source_files or not py_files:
        return False
    context_roots = {
        "examples", "example", "tests", "test", "docs", "doc", "templates", ".templates", "_pages", "tools",
        "integration-test", "integration_test", "integration_tests",
    }
    support_files = {"setup.py", "noxfile.py", "conftest.py", "release.py", "tasks.py", "_.py"}
    return all(
        file.relative_to(path).parts[0].lower() in context_roots
        or file.name.lower() in support_files
        or (file.relative_to(path).parts[0].lower() == "scripts" and (len(file.stem) <= 2 or "tmp" in file.stem.lower()))
        for file in py_files
    )


def _independent_project_collection(path: Path) -> bool:
    if _has_project_manifest(path) or _root_python_package(path):
        return False
    roots = [child for child in path.iterdir() if child.is_dir() and child.name.lower() in {"projects", "recipes"}]
    if len(roots) != 1:
        return False
    members = [child for child in roots[0].iterdir() if child.is_dir()]
    return sum(bool(_files_with_suffixes(child, {".py"})) for child in members) >= 10


def _documentation_led_demo(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if _has_project_manifest(path) or root_package or len(python_source_files) > 2:
        return False
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    if "src" not in top_dirs or not top_dirs.intersection({"data", "images", "assets", "notebooks"}):
        return False
    readmes = [child for child in path.iterdir() if child.is_file() and child.name.lower().startswith("readme")]
    return bool(readmes) and max(file.stat().st_size for file in readmes) >= 20_000


def _documentation_code_examples(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if _has_project_manifest(path) or root_package or not python_source_files:
        return False
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    if not {"code", "docs", "notebooks"}.issubset(top_dirs):
        return False
    root_modules = {child.name.lower() for child in path.glob("*.py")}
    if root_modules.intersection({"main.py", "app.py", "manage.py", "train.py"}):
        return False
    return all(file.relative_to(path).parts[0].lower() in {"code", "docs"} for file in python_source_files)


def _documentation_index_with_fetch_script(
    path: Path, python_source_files: list[Path], root_package: str | None
) -> bool:
    if _has_project_manifest(path) or root_package or not 1 <= len(python_source_files) <= 2:
        return False
    if not all(file.parent == path and file.stem.lower().startswith(("fetch", "download", "scrape")) for file in python_source_files):
        return False
    readmes = [file for file in path.iterdir() if file.is_file() and file.name.lower().startswith("readme")]
    return bool(readmes) and max(file.stat().st_size for file in readmes) >= 20_000


def _native_extension_wrapper_without_python_core(python_source_files: list[Path], rust_files: list[Path]) -> bool:
    active = [file for file in python_source_files if file.name.lower() not in {"release.py", "build.py", "noxfile.py"}]
    if not rust_files or len(active) != 1:
        return False
    source = active[0].as_posix().lower()
    return source.endswith("/__init__.py") or source == "__init__.py"


def _cpp_extension_wrapper_without_python_core(
    top_files: set[str],
    root_package: str | None,
    python_source_files: list[Path],
    cpp_files: list[Path],
) -> bool:
    if not cpp_files or root_package or not top_files.intersection({"setup.py", "pyproject.toml"}):
        return False
    active = [file for file in python_source_files if file.name.lower() not in {"release.py", "build.py", "noxfile.py"}]
    return len(active) <= 1 and len(cpp_files) >= len(active)


def _cython_extension_wrapper_without_python_core(
    top_files: set[str], root_package: str | None, python_source_files: list[Path], cython_files: list[Path]
) -> bool:
    if not cython_files or not top_files.intersection({"setup.py", "pyproject.toml"}):
        return False
    active = [file for file in python_source_files if file.name.lower() != "__init__.py"]
    return bool(root_package) and not active


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
    if any(child.name in {"src", "app", "tests"} and _files_with_suffixes(child, {".py"}) for child in children):
        return True
    py_files = _files_with_suffixes(path, {".py"})
    if len(py_files) >= 20 and any(_python_source_like(rel.relative_to(path)) for rel in py_files[:200]):
        return True
    return False


def _has_project_manifest(path: Path) -> bool:
    return any((path / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"))


def _python_role_source_file(path: Path) -> bool:
    normalized = path.as_posix().lower()
    excluded = {"tests", "test", "docs", "examples", "example", "scripts", ".github", "ci", "templates", ".templates", "_pages", "tools"}
    excluded.update({"bench", "benchmark", "benchmarks", "integration", "integration-test", "integration_test", "integration_tests"})
    if "scenarios/example_fixture/" in normalized:
        return False
    if any(part in excluded for part in normalized.split("/")):
        return False
    if path.name.lower() in {"setup.py", "noxfile.py", "conftest.py", "release.py", "tasks.py", "_.py"}:
        return False
    if "test" in path.name.lower() or path.name.lower().endswith("_template.py"):
        return False
    return True


def _root_python_package(path: Path) -> str | None:
    excluded = {
        "tests", "test", "docs", "examples", "scripts", "crates", "bench", "benchmark", "benchmarks",
        "integration", "integration-test", "integration_test", "integration_tests",
    }
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


def _files_with_suffixes(path: Path, suffixes: set[str]) -> list[Path]:
    rows: list[Path] = []
    excluded = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    for current, dirs, files in os.walk(path, topdown=True, onerror=lambda _exc: None):
        dirs[:] = [name for name in dirs if name not in excluded]
        current_path = Path(current)
        for name in files:
            if Path(name).suffix.lower() in suffixes:
                rows.append(current_path / name)
    return rows
