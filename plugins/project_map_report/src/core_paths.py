"""Path classification helpers for project analysis reports."""

from __future__ import annotations


def is_core_path(path: str) -> bool:
    return classify_source_path(path)["kind"] == "active_core"


def classify_source_path(path: str) -> dict[str, str]:
    lowered = path.replace("\\", "/").lower()
    parts = lowered.split("/")
    name = parts[-1] if parts else lowered
    stem = name[:-3] if name.endswith(".py") else name
    if name.startswith("project_analyzer_old") or lowered.startswith("_project_analyzer_") or name == "project_analyzer.py":
        return {"path": path, "kind": "legacy_noise", "reason": "legacy_project_analyzer_branch"}
    if any(
        part in {
            ".github",
            "bench",
            "benchmarks",
            "docs",
            "examples",
            "generated",
            "ci_tools",
            "downstream",
            "failures-to-investigate",
            "scripts",
            "scratch",
            "tasks",
            "test",
            "tests",
            "tools",
            "__pycache__",
        }
        for part in parts
    ):
        return {"path": path, "kind": "context_only", "reason": "non_core_context_directory"}
    if parts[:2] == ["packaging", "pep517_backend"]:
        return {"path": path, "kind": "context_only", "reason": "build_backend_context"}
    if (
        name.startswith(("make_", "build_", "setup_"))
        or name.endswith(("_benchmark.py", "_bench.py"))
        or name in {"benchmark.py", "bench.py", "noxfile.py", "setup.py"}
    ):
        return {"path": path, "kind": "context_only", "reason": "build_or_packaging_helper"}
    if (
        name == "conftest.py"
        or name in {"testclient.py", "testing.py"}
        or name.startswith("test_")
        or name.endswith("_test.py")
        or stem == "test"
        or (stem.startswith("test") and stem[4:].isdigit())
    ):
        return {"path": path, "kind": "context_only", "reason": "test_harness"}
    if any(part.endswith("_install_package") for part in parts):
        return {"path": path, "kind": "packaged_copy", "reason": "duplicated_packaged_copy"}
    if parts and parts[0].startswith("p004"):
        return {"path": path, "kind": "active_core", "reason": "active_p004_family"}
    return {"path": path, "kind": "active_core", "reason": "default_core_source"}
