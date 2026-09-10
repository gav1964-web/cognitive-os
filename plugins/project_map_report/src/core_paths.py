"""Path classification helpers for project analysis reports."""

from __future__ import annotations


def is_core_path(path: str) -> bool:
    return classify_source_path(path)["kind"] == "active_core"


def classify_source_path(path: str) -> dict[str, str]:
    lowered = path.replace("\\", "/").lower()
    parts = lowered.split("/")
    name = parts[-1] if parts else lowered
    stem = name[:-3] if name.endswith(".py") else name
    if "fixlog" in parts or any(part.startswith("attempt_") for part in parts):
        return {"path": path, "kind": "context_only", "reason": "generated_fix_attempt_log"}
    if "workspace" in parts:
        return {"path": path, "kind": "context_only", "reason": "generated_runtime_workspace"}
    if any(_is_generated_context_part(part) for part in parts):
        return {"path": path, "kind": "context_only", "reason": "generated_context_directory"}
    if name.startswith("pipeline_backup_") or "_backup_" in name:
        return {"path": path, "kind": "legacy_noise", "reason": "generated_backup_snapshot"}
    if len(parts) >= 2 and parts[0] == "vx" and parts[1] == "autofix":
        return {"path": path, "kind": "packaged_copy", "reason": "nested_project_copy"}
    if len(parts) >= 2 and _looks_like_snapshot_dir(parts[0]):
        return {"path": path, "kind": "packaged_copy", "reason": "nested_snapshot_copy"}
    if name.startswith("project_analyzer_old") or lowered.startswith("_project_analyzer_") or name == "project_analyzer.py":
        return {"path": path, "kind": "legacy_noise", "reason": "legacy_project_analyzer_branch"}
    if any(
        part in {
            ".github",
            "_testing",
            "bench",
            "benchmarks",
            "doc",
            "docs",
            "docs_src",
            "dummyserver",
            "examples",
            "extras",
            "generated",
            "fixlog",
            "ci_tools",
            "downstream",
            "failures-to-investigate",
            "external-deps",
            "scripts",
            "scratch",
            "tasks",
            "template",
            "test",
            "tests",
            "testing",
            "tools",
            "wasm-preview",
            "workspace",
            "__pycache__",
        }
        for part in parts
    ):
        return {"path": path, "kind": "context_only", "reason": "non_core_context_directory"}
    if any(_is_test_context_part(part) for part in parts):
        return {"path": path, "kind": "context_only", "reason": "test_or_fixture_context_directory"}
    if parts[:2] == ["packaging", "pep517_backend"]:
        return {"path": path, "kind": "context_only", "reason": "build_backend_context"}
    if "waflib" in parts:
        return {"path": path, "kind": "context_only", "reason": "vendored_build_helper"}
    if (
        name.startswith(("make_", "build_", "setup_"))
        or name.endswith(("_benchmark.py", "_bench.py"))
        or name in {"benchmark.py", "bench.py", "noxfile.py", "setup.py", "runtests.py", "run_tests.py", "hatch_build.py", "install_dev_repos.py"}
        or name in {"documentation.py", "docs.py"}
    ):
        return {"path": path, "kind": "context_only", "reason": "build_or_packaging_helper"}
    if "integrations" in parts and ("aws" in parts or any(part.startswith("prefect-") for part in parts)):
        return {"path": path, "kind": "context_only", "reason": "optional_integration_adapter"}
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


def _is_generated_context_part(part: str) -> bool:
    return part == "generated" or part.startswith("generated_") or part.startswith("generated-")


def _is_test_context_part(part: str) -> bool:
    normalized = part.replace("-", "_")
    return (
        normalized in {"fixture", "fixtures", "testdata", "test_data"}
        or normalized.startswith(("e2e_test", "integration_test"))
        or normalized.endswith(("_test", "_tests"))
        or normalized.startswith("test")
    )


def _looks_like_snapshot_dir(part: str) -> bool:
    lowered = part.lower()
    if lowered.endswith(("_backup", "-backup", "_copy", "-copy")):
        return True
    chunks = lowered.replace("-", "_").split("_")
    return any(len(chunk) == 8 and chunk.isdigit() and chunk.startswith(("20", "19")) for chunk in chunks)
