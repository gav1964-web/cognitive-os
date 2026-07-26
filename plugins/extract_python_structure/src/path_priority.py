"""Path ordering helpers for Python structure extraction."""

from __future__ import annotations

from pathlib import Path


EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
LATE_DIRS = {
    "_testing",
    "artifacts",
    "build",
    "dist",
    "doc",
    "docs",
    "docs_src",
    "examples",
    "extras",
    "generated",
    "scratch",
    "testing",
    "tests",
    "tools",
}
EARLY_DIRS = {
    "airflow",
    "airflow-core",
    "app",
    "apps",
    "borg",
    "core",
    "dask",
    "gradio",
    "lib",
    "mitmproxy",
    "packages",
    "prefect",
    "pyinstaller",
    "scrapy",
    "spyder",
    "src",
}
EARLY_FILES = {"api_server.py", "app.py", "main.py", "server.py", "api.py", "__init__.py"}


def iter_python_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        dirs = []
        files = []
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for item in children:
            try:
                is_dir = item.is_dir()
                is_file = item.is_file()
            except OSError:
                continue
            if is_dir:
                if item.name in EXCLUDED_DIRS or _is_generated_context_dir(item.name) or item.name.startswith("."):
                    continue
                dirs.append(item)
            elif is_file and item.suffix.lower() == ".py":
                files.append(item)
        for item in sorted(files, key=traversal_key):
            yield item
        stack.extend(reversed(sorted(dirs, key=traversal_key)))


def is_test_path(path: str) -> bool:
    name = Path(path).name
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py")


def traversal_key(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if path.is_dir():
        if name in EARLY_DIRS:
            return (0, name)
        if name in LATE_DIRS or _is_generated_context_dir(name):
            return (9, name)
        return (3, name)
    if name in EARLY_FILES:
        return (0, name)
    return (3, name)


def path_priority(path: str) -> int:
    lowered = path.replace("\\", "/").lower()
    parts = lowered.split("/")
    name = parts[-1] if parts else lowered
    if any(
        part
        in {
            "tests",
            "test",
            "_testing",
            "bench",
            "benchmarks",
            "ci_tools",
            "doc",
            "docs",
            "docs_src",
            "downstream",
            "examples",
            "extras",
            "failures-to-investigate",
            "integration",
            "scripts",
            "tasks",
            "testing",
            "tools",
        }
        for part in parts
    ) or any(_is_generated_context_dir(part) for part in parts):
        return 9
    helper_names = {"benchmark.py", "bench.py", "noxfile.py", "conftest.py", "testclient.py", "testing.py"}
    if parts[:2] == ["packaging", "pep517_backend"] or name.endswith(("_benchmark.py", "_bench.py")) or name in helper_names:
        return 8
    if lowered.startswith("src/") or "/src/" in lowered:
        return 0
    if lowered.startswith(("airflow/", "airflow-core/", "app/", "lib/", "packages/")) or "/" not in lowered and name in EARLY_FILES:
        return 1
    if any(part in {"borg", "dask", "gradio", "mitmproxy", "prefect", "pyinstaller", "scrapy", "spyder"} for part in parts[:2]):
        return 1
    return 3


def _is_generated_context_dir(name: str) -> bool:
    lowered = name.lower()
    return lowered == "generated" or lowered.startswith("generated_") or lowered.startswith("generated-")
