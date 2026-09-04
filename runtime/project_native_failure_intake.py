"""Compatibility facade for project-native failure intake."""

from __future__ import annotations

import venv

from .project_native_failure_binding import (
    _case_status,
    _failure_kind,
    _interpret_pytest_result,
    _last_failure_line,
    _normalize_nodeid,
    _source_fallback_plugin_metadata_failure,
)
from .project_native_failure_collection import _collected_nodeids
from .project_native_failure_environment import (
    _configure_short_basetemp,
    _hermetic_user_environment,
    _interpreter_candidates,
    _prepare_local_project,
    _probe_python_version,
    _project_distribution_name,
    _project_specific_intake,
    _pytest_arguments,
    _pytest_basetemp_target,
    _resolve_project_interpreter,
    _write_probe_path_bootstrap,
)
from .project_native_failure_process import (
    _copy_git_build_metadata,
    _copy_project,
    _git_metadata_source,
    _project_digest,
    _project_version_hint,
    _run_bounded_process,
    _slug,
    _terminate_process_tree,
)
from .project_native_failure_intake_core import (
    _intake_work_root,
    _run_project_case,
    _validated_test_targets,
    run_project_native_failure_intake,
    run_project_native_verification,
)
from .project_native_failure_pytest import (
    _native_pytest_targets,
    _pytest9_collection_compatibility_failure,
    _run_pytest,
    _run_pytest_shards,
    _run_refined_pytest_shards,
    _test_file_shards,
)
from .project_native_failure_shard_cache import (
    _configured_overlay_digest,
    _load_cached_shard_pass,
    _shard_cache_key,
    _store_cached_shard_pass,
)
from .project_native_failure_target_binding import (
    _assertion_causal_calls,
    _assignment_names,
    _attribute_names,
    _direct_test_call_targets,
    _excluded_call_reason,
    _imported_call_target,
    _is_production_path,
    _lexical_function_nodes,
    _named_constructor_failure_target,
    _production_targets,
    _project_relative_traceback_path,
    _python_module_path,
    _python_module_path_any,
    _source_defines_symbol,
    _symbol_at_line,
    _test_assertion_causal_analysis,
    _test_import_aliases,
    _unique_state_transition_target,
)
