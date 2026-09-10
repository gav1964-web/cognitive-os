from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from runtime import foundation_scope_boundaries as scope_boundaries
from runtime.source_target_policy import scope_policy_int, scope_policy_list
from runtime._parts.role_foundation_field_trial_scope_helpers import (
    child_python_projects as _child_python_projects,
    cpp_extension_wrapper_without_python_core as _cpp_extension_wrapper_without_python_core,
    cython_extension_wrapper_without_python_core as _cython_extension_wrapper_without_python_core,
    distributed_project_portfolio as _distributed_project_portfolio,
    documentation_code_examples as _documentation_code_examples,
    documentation_index_with_fetch_script as _documentation_index_with_fetch_script,
    documentation_led_demo as _documentation_led_demo,
    examples_only_python_corpus as _examples_only_python_corpus,
    has_project_manifest as _has_project_manifest,
    incidental_python_automation as _incidental_python_automation,
    incidental_python_support as _incidental_python_support,
    independent_project_collection as _independent_project_collection,
    is_python_project as _is_python_project,
    is_workspace_portfolio_candidate as _is_workspace_portfolio_candidate,
    native_extension_wrapper_without_python_core as _native_extension_wrapper_without_python_core,
    python_role_source_file as _python_role_source_file,
    python_source_like as _python_source_like,
    root_python_package as _root_python_package,
    type_stub_corpus as _type_stub_corpus,
)


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
    foreign_extensions = set(scope_policy_list("foreign_language_source_extensions"))
    foreign_files = _files_with_suffixes(path, foreign_extensions) if foreign_extensions else []
    python_source_files = [file for file in py_files if _python_role_source_file(file.relative_to(path))]
    root_package = _root_python_package(path)
    has_root_python_source = bool(root_package or (path / "src").is_dir() or (path / "app").is_dir())
    c_runtime_core = (
        len(c_files) >= 100
        and not root_package
        and {"include", "modules"}.issubset(top_dirs)
        and bool({"objects", "python"}.intersection(top_dirs))
    )
    cpp_minimum = scope_policy_int("cpp_runtime_core_min_files", 10)
    cpp_runtime_core = (
        len(cpp_files) >= max(cpp_minimum, len(python_source_files))
        and not root_package
        and "src" in top_dirs
    )
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
        or _distributed_project_portfolio(path, py_files)
        or _incidental_python_support(path, python_source_files, root_package)
        or _incidental_python_automation(path, python_source_files, root_package)
        or scope_boundaries.incidental_context_scripts(path, python_source_files, root_package)
        or scope_boundaries.native_dominated_monorepo(native_files, py_files, root_package)
        or scope_boundaries.native_binding_support_only(path, python_source_files, native_files, root_package)
        or scope_boundaries.foreign_language_dominated_monorepo(foreign_files, py_files, root_package)
        or scope_boundaries.fixture_only_python_corpus(path, py_files, root_package)
        or scope_boundaries.scripts_only_python_support(path, py_files, root_package)
        or scope_boundaries.curriculum_exercise_corpus(path, py_files, root_package)
        or scope_boundaries.documentation_deployment_demo(path, python_source_files, root_package)
        or scope_boundaries.incidental_polyglot_python_boundary(
            path, python_source_files, root_package, has_manifest=_has_project_manifest(path)
        )
        or scope_boundaries.django_scaffold_without_owned_app(
            python_source_files, root_package, has_manifest=_has_project_manifest(path)
        )
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
