from __future__ import annotations

import os
import re
from pathlib import Path

from runtime.source_target_policy import scope_policy_int, scope_policy_list


def type_stub_corpus(top_dirs: set[str], py_files: list[Path], pyi_files: list[Path]) -> bool:
    if not {"stdlib", "stubs"}.issubset(top_dirs):
        return False
    return len(pyi_files) >= max(200, len(py_files) * 10)


def examples_only_python_corpus(path: Path, py_files: list[Path], python_source_files: list[Path]) -> bool:
    if len(python_source_files) == 1 and " " in python_source_files[0].name and not has_project_manifest(path):
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


def independent_project_collection(path: Path) -> bool:
    if has_project_manifest(path) or root_python_package(path):
        return False
    roots = [child for child in path.iterdir() if child.is_dir() and child.name.lower() in {"projects", "recipes"}]
    if len(roots) != 1:
        return False
    members = [child for child in roots[0].iterdir() if child.is_dir()]
    return sum(bool(files_with_suffixes(child, {".py"})) for child in members) >= 10


def distributed_project_portfolio(path: Path, py_files: list[Path]) -> bool:
    if (
        has_project_manifest(path)
        or root_python_package(path)
        or len(py_files) < scope_policy_int("portfolio_min_python_files", 1_000)
    ):
        return False
    python_roots = {file.relative_to(path).parts[0].lower() for file in py_files}
    nested_manifests = 0
    manifest_names = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}
    excluded = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    for current, dirs, files in os.walk(path, topdown=True, onerror=lambda _exc: None):
        dirs[:] = [name for name in dirs if name not in excluded]
        if Path(current) != path:
            nested_manifests += sum(name.lower() in manifest_names for name in files)
    return (
        len(python_roots) >= scope_policy_int("portfolio_min_python_roots", 4)
        and nested_manifests >= scope_policy_int("portfolio_min_nested_manifests", 20)
    )


def incidental_python_support(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if has_project_manifest(path) or root_package or not 1 <= len(python_source_files) <= 2:
        return False
    relative = [file.relative_to(path) for file in python_source_files]
    root_product_modules = set(scope_policy_list("incidental_python_product_modules"))
    if any(len(file.parts) == 1 and file.name.lower() in root_product_modules for file in relative):
        return False
    support_modules = set(scope_policy_list("incidental_python_support_modules"))
    if all(file.name.lower() in support_modules for file in relative):
        return True
    product_roots = set(scope_policy_list("incidental_python_product_roots"))
    return all(len(file.parts) >= 2 and file.parts[0].lower() not in product_roots for file in relative)


def incidental_python_automation(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if root_package or not python_source_files:
        return False
    strong_manifests = ("pyproject.toml", "setup.py", "setup.cfg")
    if any((path / name).is_file() for name in strong_manifests):
        return False
    maximum = scope_policy_int("incidental_python_automation_max_files", 20)
    if len(python_source_files) > maximum:
        return False
    roots = set(scope_policy_list("incidental_python_automation_roots"))
    return all(file.relative_to(path).parts[0].lower() in roots for file in python_source_files)


def documentation_led_demo(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if has_project_manifest(path) or root_package or len(python_source_files) > 2:
        return False
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    if "src" not in top_dirs or not top_dirs.intersection({"data", "images", "assets", "notebooks"}):
        return False
    readmes = [child for child in path.iterdir() if child.is_file() and child.name.lower().startswith("readme")]
    return bool(readmes) and max(file.stat().st_size for file in readmes) >= 20_000


def documentation_code_examples(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if has_project_manifest(path) or root_package or not python_source_files:
        return False
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    if not {"code", "docs", "notebooks"}.issubset(top_dirs):
        return False
    root_modules = {child.name.lower() for child in path.glob("*.py")}
    if root_modules.intersection({"main.py", "app.py", "manage.py", "train.py"}):
        return False
    return all(file.relative_to(path).parts[0].lower() in {"code", "docs"} for file in python_source_files)


def documentation_index_with_fetch_script(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if has_project_manifest(path) or root_package or not 1 <= len(python_source_files) <= 2:
        return False
    if not all(file.parent == path and file.stem.lower().startswith(("fetch", "download", "scrape")) for file in python_source_files):
        return False
    readmes = [file for file in path.iterdir() if file.is_file() and file.name.lower().startswith("readme")]
    return bool(readmes) and max(file.stat().st_size for file in readmes) >= 20_000


def native_extension_wrapper_without_python_core(python_source_files: list[Path], rust_files: list[Path]) -> bool:
    active = [file for file in python_source_files if file.name.lower() not in {"release.py", "build.py", "noxfile.py"}]
    if not rust_files or len(active) != 1:
        return False
    source = active[0].as_posix().lower()
    return source.endswith("/__init__.py") or source == "__init__.py"


def cpp_extension_wrapper_without_python_core(
    top_files: set[str],
    root_package: str | None,
    python_source_files: list[Path],
    cpp_files: list[Path],
) -> bool:
    if not cpp_files or root_package or not top_files.intersection({"setup.py", "pyproject.toml"}):
        return False
    active = [file for file in python_source_files if file.name.lower() not in {"release.py", "build.py", "noxfile.py"}]
    return len(active) <= 1 and len(cpp_files) >= len(active)


def cython_extension_wrapper_without_python_core(
    top_files: set[str], root_package: str | None, python_source_files: list[Path], cython_files: list[Path]
) -> bool:
    if not cython_files or not top_files.intersection({"setup.py", "pyproject.toml"}):
        return False
    active = [file for file in python_source_files if file.name.lower() != "__init__.py"]
    return bool(root_package) and not active


def child_python_projects(path: Path) -> list[Path]:
    return [child.resolve() for child in sorted(path.iterdir()) if child.is_dir() and is_python_project(child)]


def is_workspace_portfolio_candidate(path: Path) -> bool:
    if has_project_manifest(path) or root_python_package(path):
        return False
    version_hint = re.compile(
        r"(?:^|[_-])(20\d{2}(?:\d{2})?|v?\d+(?:\.\d+)*|current|active|next|candidate|rewrite|legacy|archive|previous|original|retired)(?:$|[_-])",
        re.IGNORECASE,
    )
    candidate_roots = []
    for child in path.iterdir():
        if not child.is_dir() or not version_hint.search(child.name):
            continue
        if files_with_suffixes(child, {".py"}):
            candidate_roots.append(child)
    return len(candidate_roots) >= 2 and any(has_project_manifest(child) for child in candidate_roots)


def is_python_project(path: Path) -> bool:
    if not path.is_dir():
        return False
    if has_project_manifest(path):
        return True
    if any(path.glob("*.py")):
        return True
    children = [child for child in path.iterdir() if child.is_dir()]
    if any(child.name in {"src", "app", "tests"} and files_with_suffixes(child, {".py"}) for child in children):
        return True
    py_files = files_with_suffixes(path, {".py"})
    if len(py_files) >= 20 and any(python_source_like(rel.relative_to(path)) for rel in py_files[:200]):
        return True
    return False


def has_project_manifest(path: Path) -> bool:
    return any((path / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"))


def python_role_source_file(path: Path) -> bool:
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


def root_python_package(path: Path) -> str | None:
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


def python_source_like(path: Path) -> bool:
    normalized = path.as_posix().lower()
    if any(token in normalized for token in ("/.git/", "/docs/", "/assets/", "/ci/", "/scripts/")):
        return False
    return "__init__.py" in normalized or "/src/" in normalized or normalized.count("/") >= 1


def files_with_suffixes(path: Path, suffixes: set[str]) -> list[Path]:
    rows: list[Path] = []
    excluded = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    for current, dirs, files in os.walk(path, topdown=True, onerror=lambda _exc: None):
        dirs[:] = [name for name in dirs if name not in excluded]
        current_path = Path(current)
        for name in files:
            if Path(name).suffix.lower() in suffixes:
                rows.append(current_path / name)
    return rows
