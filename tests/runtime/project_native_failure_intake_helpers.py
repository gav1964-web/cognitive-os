from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.project_native_failure_intake import (
    _hermetic_user_environment,
    _intake_work_root,
    _native_pytest_targets,
    _test_file_shards,
    _collected_nodeids,
    _normalize_nodeid,
    _write_probe_path_bootstrap,
    _shard_cache_key,
    _load_cached_shard_pass,
    _store_cached_shard_pass,
    _project_digest,
    _project_version_hint,
    _prepare_local_project,
    _pytest_arguments,
    _project_specific_intake,
    _named_constructor_failure_target,
    _production_targets,
    _test_assertion_causal_analysis,
    _resolve_project_interpreter,
    _configured_overlay_digest,
    _run_bounded_process,
    _copy_git_build_metadata,
    _interpret_pytest_result,
    _failure_kind,
    _pytest9_collection_compatibility_failure,
    _direct_test_call_targets,
    run_project_native_failure_intake,
    run_project_native_verification,
)
































































































































def _write_project(root, *, failing: bool) -> None:
    (root / "tests").mkdir(parents=True)
    body = "raise ValueError('broken normalization')" if failing else "return value.strip().lower()"
    (root / "core.py").write_text(
        f"def normalize(value):\n    {body}\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_core.py").write_text(
        "from core import normalize\n\n"
        "def test_normalize():\n"
        "    assert normalize(' A ') == 'a'\n",
        encoding="utf-8",
    )













__all__ = [name for name in globals() if not name.startswith("__")]
