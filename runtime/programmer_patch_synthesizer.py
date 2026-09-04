"""Compatibility facade for deterministic programmer patch synthesis."""

from __future__ import annotations

from .programmer_patch_synthesizer_common import (
    NO_PATCH,
    _copy_project,
    _expected_files,
    _patch_result,
    _recovery_patch_digest,
    _remove_tree,
    _target_symbol,
)
from .programmer_patch_synthesizer_contract_packages import (
    _duplicate_cli_option_package,
    _framework_contract_package,
    _falsy_primitive_empty_package,
    _fstring_brace_offset_package,
    _incomplete_import_token_package,
    _registry_fallback_package,
    _strict_default_comparison_package,
    _timestamp_range_error_package,
    _trailing_backslash_bounds_package,
)
from .programmer_patch_synthesizer_core import synthesize_patch_package
from .programmer_patch_synthesizer_guard import (
    _body_indent,
    _defaulted_parameters,
    _find_patchable_function,
    _function_already_has_guard,
    _guard_evidence,
    _guard_insert_line,
    _guard_lines,
    _guard_required_keys,
    _patch_required_input_guard,
    _required_input_keys,
    _required_signature_keys,
)
from .programmer_patch_synthesizer_helper_extractors import (
    _call_name,
    _enclosing_loop,
    _extract_append_mapping_helper,
    _extract_json_dumps_helper,
    _extract_json_loads_helper,
    _extract_splitlines_helper,
    _find_top_level_function,
    _parent_map,
    _returns_name,
)
from .programmer_patch_synthesizer_recovery import (
    _development_helper_extraction_package,
    synthesize_recovery_patch_package,
)
