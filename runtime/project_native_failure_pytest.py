"""Bounded pytest execution and sharding for project-native intake."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .project_native_failure_binding import _interpret_pytest_result
from .project_native_failure_collection import _collected_nodeids
from .project_native_failure_environment import (
    _hermetic_user_environment,
    _prepare_local_project,
    _pytest_arguments,
    _run_bounded_process,
)
from .project_native_failure_shard_cache import _load_cached_shard_pass, _shard_cache_key, _store_cached_shard_pass

def _run_pytest(
    project: Path, intake: dict[str, Any], *, nodeids: list[str] | None = None
) -> dict[str, Any]:
    resolution = dict(intake.get("interpreter_resolution") or {})
    if resolution.get("status") == "unavailable":
        return {
            "status": "environment_blocked",
            "exit_code": None,
            "failure_signature": None,
            "failing_nodeids": [],
            "production_targets": [],
            "failure_summary": "required Python interpreter is unavailable",
            "environment_reason": "required_interpreter_unavailable",
            "interpreter_resolution": resolution,
            "output_tail": "",
        }
    python, preparation = _prepare_local_project(project, intake)
    if preparation.get("status") == "failed":
        return {
            "status": "environment_blocked",
            "exit_code": preparation.get("exit_code"),
            "failure_signature": None,
            "failing_nodeids": [],
            "production_targets": [],
            "failure_summary": "local editable install failed without dependency resolution",
            "environment_preparation": preparation,
            "output_tail": str(preparation.get("output_tail") or ""),
        }
    test_targets = _native_pytest_targets(project, nodeids)
    command = [
        str(python), "-m", "pytest",
        *_pytest_arguments(project, intake),
        *test_targets,
    ]
    env = dict(os.environ)
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": (
            "1" if bool(intake.get("disable_external_pytest_plugin_autoload", True)) else "0"
        ),
    })
    env.update(_hermetic_user_environment(project, intake))
    nested_plugins = [str(value) for value in intake.get("nested_pytest_plugins") or []]
    if nested_plugins:
        env["PYTEST_PLUGINS"] = ",".join(nested_plugins)
    import_roots = [str(project)] if bool(intake.get("probe_path_bootstrap", True)) else []
    if bool(intake.get("probe_path_bootstrap", True)) and (project / "src").is_dir():
        import_roots.append(str(project / "src"))
    if intake.get("dependency_overlay_path"):
        import_roots.append(str(intake["dependency_overlay_path"]))
    if intake.get("tool_overlay_path") and intake.get("tool_overlay_path") not in import_roots:
        import_roots.append(str(intake["tool_overlay_path"]))
    if env.get("PYTHONPATH"):
        import_roots.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(import_roots)
    try:
        completed = _run_bounded_process(
            command,
            cwd=project,
            env=env,
            timeout=max(1, int(intake.get("timeout_seconds") or 120)),
        )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        result = _interpret_pytest_result(
            project, completed.returncode, output, intake,
            environment_preparation=preparation,
        )
        if (
            _pytest9_collection_compatibility_failure(output)
            and "ignore::pytest.PytestRemovedIn10Warning"
            not in [str(value) for value in intake.get("pytest_arguments") or []]
        ):
            compatibility_intake = dict(intake)
            compatibility_intake["pytest_arguments"] = [
                *[str(value) for value in intake.get("pytest_arguments") or []],
                "-W",
                "ignore::pytest.PytestRemovedIn10Warning",
            ]
            retried = _run_pytest(project, compatibility_intake, nodeids=nodeids)
            retried["compatibility_retry"] = {
                "kind": "pytest9_removed_warning_compatibility",
                "trigger": "PytestRemovedIn10Warning during collection",
                "project_source_changes": False,
            }
            return retried
        result["environment_preparation"] = preparation
        result["interpreter_resolution"] = resolution
        result["test_targets"] = test_targets
        return result
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        if not nodeids and bool(intake.get("shard_on_timeout", True)):
            shards = _test_file_shards(project, intake)
            if shards:
                return _run_pytest_shards(
                    project=project,
                    python=python,
                    env=env,
                    preparation=preparation,
                    intake=intake,
                    shards=shards,
                )
        return {
            "status": "timeout",
            "exit_code": None,
            "failure_signature": None,
            "failing_nodeids": [],
            "production_targets": [],
            "failure_summary": "pytest baseline exceeded the bounded timeout",
            "output_tail": output[-int(intake.get("maximum_output_chars") or 12000):],
            "environment_preparation": preparation,
            "test_targets": test_targets,
        }

def _pytest9_collection_compatibility_failure(output: str) -> bool:
    return (
        "pytest.PytestRemovedIn10Warning: Passing a non-Collection iterable to parametrize"
        in output
        and "ERROR collecting" in output
    )

def _native_pytest_targets(project: Path, nodeids: list[str] | None) -> list[str]:
    if nodeids:
        return list(nodeids)
    legacy_suite = project / "tests.py"
    if not legacy_suite.is_file():
        return []
    default_candidates = {
        path
        for pattern in ("test_*.py", "*_test.py")
        for path in project.rglob(pattern)
        if path.is_file()
    }
    return [] if default_candidates else ["tests.py"]

def _test_file_shards(project: Path, intake: dict[str, Any]) -> list[list[str]]:
    tests_root = project / "tests"
    if not tests_root.is_dir():
        return []
    files = sorted(
        {
            path
            for pattern in ("test_*.py", "*_test.py")
            for path in tests_root.rglob(pattern)
            if path.is_file()
        },
        key=lambda path: path.relative_to(project).as_posix(),
    )
    maximum_files = max(1, int(intake.get("maximum_shard_test_files") or 240))
    if not files or len(files) > maximum_files:
        return []
    shard_count = min(max(1, int(intake.get("maximum_shards") or 6)), len(files))
    buckets: list[tuple[int, list[str]]] = [(0, []) for _ in range(shard_count)]
    weighted = sorted(files, key=lambda path: (-path.stat().st_size, path.relative_to(project).as_posix()))
    for path in weighted:
        index = min(range(shard_count), key=lambda item: (buckets[item][0], item))
        weight, members = buckets[index]
        members.append(path.relative_to(project).as_posix())
        buckets[index] = (weight + path.stat().st_size, members)
    return [sorted(members) for _, members in buckets if members]

def _run_pytest_shards(
    *,
    project: Path,
    python: Path,
    env: dict[str, str],
    preparation: dict[str, Any],
    intake: dict[str, Any],
    shards: list[list[str]],
) -> dict[str, Any]:
    outputs: list[str] = []
    limit = int(intake.get("maximum_output_chars") or 12000)
    for index, nodeids in enumerate(shards, start=1):
        cache_key = _shard_cache_key(project, nodeids, intake, mode="coarse")
        if cache_key and _load_cached_shard_pass(cache_key, intake):
            outputs.append(f"shard {index}: cached pass")
            continue
        command = [
            str(python),
            "-m",
            "pytest",
            *_pytest_arguments(project, intake),
            *nodeids,
        ]
        try:
            completed = _run_bounded_process(
                command,
                cwd=project,
                env=env,
                timeout=max(1, int(intake.get("shard_timeout_seconds") or 60)),
            )
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + (
                (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            )
            refined = _run_refined_pytest_shards(
                project=project,
                python=python,
                env=env,
                preparation=preparation,
                intake=intake,
                nodeids=nodeids,
                parent_shard=index,
            )
            if refined and refined.get("status") == "passed":
                if cache_key:
                    _store_cached_shard_pass(cache_key, intake, nodeids, mode="coarse")
                outputs.append(str(refined.get("output_tail") or ""))
                continue
            if refined:
                return refined
            return {
                "status": "timeout",
                "exit_code": None,
                "failure_signature": None,
                "failing_nodeids": [],
                "production_targets": [],
                "failure_summary": "pytest shard exceeded the bounded timeout",
                "output_tail": output[-limit:],
                "environment_preparation": preparation,
                "execution_mode": "sharded_after_timeout",
                "shard_count": len(shards),
                "failed_shard": index,
            }
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        outputs.append(output[-limit:])
        result = _interpret_pytest_result(
            project, completed.returncode, output, intake,
            environment_preparation=preparation,
        )
        if result["status"] != "passed":
            result.update(
                {
                    "environment_preparation": preparation,
                    "execution_mode": "sharded_after_timeout",
                    "shard_count": len(shards),
                    "failed_shard": index,
                    "output_tail": output[-limit:],
                }
            )
            return result
        if cache_key:
            _store_cached_shard_pass(cache_key, intake, nodeids, mode="coarse")
    return {
        "status": "passed",
        "exit_code": 0,
        "failure_signature": None,
        "failing_nodeids": [],
        "production_targets": [],
        "leaf_production_target": None,
        "target_binding": None,
        "failure_summary": "pytest shards passed",
        "output_tail": "\n".join(outputs)[-limit:],
        "environment_preparation": preparation,
        "execution_mode": "sharded_after_timeout",
        "shard_count": len(shards),
    }

def _run_refined_pytest_shards(
    *,
    project: Path,
    python: Path,
    env: dict[str, str],
    preparation: dict[str, Any],
    intake: dict[str, Any],
    nodeids: list[str],
    parent_shard: int,
) -> dict[str, Any] | None:
    collect_command = [
        str(python),
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        *nodeids,
    ]
    try:
        collected = _run_bounded_process(
            collect_command,
            cwd=project,
            env=env,
            timeout=max(1, int(intake.get("shard_collection_timeout_seconds") or 30)),
        )
    except subprocess.TimeoutExpired:
        return None
    if collected.returncode != 0:
        return None
    discovered = _collected_nodeids(collected.stdout or "", intake)
    if not discovered:
        return None
    refined_count = min(
        max(2, int(intake.get("maximum_refined_shards") or 16)), len(discovered)
    )
    groups = [discovered[index::refined_count] for index in range(refined_count)]
    outputs: list[str] = []
    limit = int(intake.get("maximum_output_chars") or 12000)
    for refined_index, group in enumerate(groups, start=1):
        cache_key = _shard_cache_key(project, group, intake, mode="refined")
        if cache_key and _load_cached_shard_pass(cache_key, intake):
            outputs.append(f"refined shard {refined_index}: cached pass")
            continue
        args_path = project.parent / f"pytest-shard-{parent_shard}-{refined_index}.txt"
        args_path.write_text("\n".join(group) + "\n", encoding="utf-8")
        command = [
            str(python),
            "-m",
            "pytest",
            *_pytest_arguments(project, intake),
            f"@{args_path}",
        ]
        try:
            completed = _run_bounded_process(
                command,
                cwd=project,
                env=env,
                timeout=max(1, int(intake.get("refined_shard_timeout_seconds") or 60)),
            )
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + (
                (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            )
            return {
                "status": "timeout",
                "exit_code": None,
                "failure_signature": None,
                "failing_nodeids": [],
                "production_targets": [],
                "failure_summary": "refined pytest shard exceeded the bounded timeout",
                "output_tail": output[-limit:],
                "environment_preparation": preparation,
                "execution_mode": "refined_shards_after_timeout",
                "failed_shard": parent_shard,
                "failed_refined_shard": refined_index,
                "refined_shard_count": refined_count,
            }
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        outputs.append(output[-limit:])
        result = _interpret_pytest_result(
            project, completed.returncode, output, intake,
            environment_preparation=preparation,
        )
        if result["status"] != "passed":
            result.update(
                {
                    "environment_preparation": preparation,
                    "execution_mode": "refined_shards_after_timeout",
                    "failed_shard": parent_shard,
                    "failed_refined_shard": refined_index,
                    "refined_shard_count": refined_count,
                    "output_tail": output[-limit:],
                }
            )
            return result
        if cache_key:
            _store_cached_shard_pass(cache_key, intake, group, mode="refined")
    return {
        "status": "passed",
        "exit_code": 0,
        "failure_signature": None,
        "failing_nodeids": [],
        "production_targets": [],
        "failure_summary": "refined pytest shards passed",
        "output_tail": "\n".join(outputs)[-limit:],
        "execution_mode": "refined_shards_after_timeout",
        "refined_shard_count": refined_count,
    }
