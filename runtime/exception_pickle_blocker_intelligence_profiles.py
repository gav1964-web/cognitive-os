"""Readmission and import-isolation profiles for exception-pickle blockers."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .exception_pickle_active_application import (
    _candidate_effective_replay_risk,
    _candidate_replay_risk,
    _candidate_static_patch_risk,
    _prefer_direct_file_replay,
)
from .exception_pickle_blocker_intelligence_common import _top
from .exception_pickle_blocker_intelligence_ledger import _semantic_replay_error


def _readmission_profile(
    root: Path,
    active_catalog: dict[str, Any],
    row: dict[str, Any],
    required: list[str],
    source_facts: dict[str, Any],
) -> dict[str, Any]:
    static_patch_risk = _candidate_static_patch_risk(root, active_catalog, row)
    replay_risk = _candidate_replay_risk(root, row)
    effective_replay_risk = _candidate_effective_replay_risk(root, row)
    fact_tags = set(source_facts.get("fact_tags") or [])
    subtype = _readmission_subtype(required, fact_tags)
    return {
        "subtype": subtype,
        "required_input_count": len(required),
        "required_input_signature": ",".join(required),
        "patchable": static_patch_risk == 0,
        "static_patch_risk": static_patch_risk,
        "replay_risk": replay_risk,
        "effective_replay_risk": effective_replay_risk,
        "direct_file_preferred": _prefer_direct_file_replay(root, row),
        "dependency_light": effective_replay_risk <= 3,
        "ready_now": static_patch_risk == 0 and effective_replay_risk <= 3,
    }


def _readmission_subtype(required: list[str], fact_tags: set[str]) -> str:
    if "parameter_method_call" in fact_tags:
        return "method_object_sample"
    if fact_tags & {"attribute_access", "mapping_access", "iterable_usage"}:
        return "source_backed_object_sample"
    if "base_exception_argument_transform" in fact_tags:
        return "derived_message_sample"
    if "direct_self_assignment" in fact_tags:
        return "direct_self_assignment_sample"
    if len(required) == 1:
        return "single_primitive_sample"
    return "mixed_supported_sample"


def _readmission_frontier_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = [
        dict(case.get("readmission_profile") or {})
        for case in cases
        if case.get("next_operator_lane") == "sample_supported_readmission_frontier"
        and isinstance(case.get("readmission_profile"), dict)
    ]
    subtype_counter: Counter[str] = Counter()
    signature_counter: Counter[str] = Counter()
    for profile in profiles:
        subtype_counter[str(profile.get("subtype") or "unknown")] += 1
        signature_counter[str(profile.get("required_input_signature") or "")] += 1
    return {
        "case_count": len(profiles),
        "ready_now_count": sum(1 for profile in profiles if profile.get("ready_now") is True),
        "patchable_count": sum(1 for profile in profiles if profile.get("patchable") is True),
        "dependency_light_count": sum(1 for profile in profiles if profile.get("dependency_light") is True),
        "subtype_summary": dict(sorted(subtype_counter.items())),
        "top_required_input_signatures": _top(signature_counter, 8),
    }


def _import_isolation_profile(
    root: Path,
    row: dict[str, Any],
    blocked: dict[str, Any],
    required: list[str],
    source_facts: dict[str, Any],
    attempt_detail: dict[str, Any],
) -> dict[str, Any]:
    fact_tags = set(source_facts.get("fact_tags") or [])
    blocker_kind = str(blocked.get("blocker_kind") or "")
    replay_error = _semantic_replay_error(blocked) or _semantic_replay_error(attempt_detail)
    missing_import = _missing_import_from_error(replay_error)
    missing_import_kind = _missing_import_kind(root, row, missing_import)
    subtype = "dependency_unavailable"
    if "attribute_base_class_definition" in fact_tags:
        subtype = "attribute_base_metaclass_risk"
    elif blocker_kind == "semantic_replay_import_failed":
        subtype = "import_failed"
    elif blocker_kind == "semantic_sample_shape_unsupported":
        subtype = "sample_supported_but_dependency_heavy"
    elif blocker_kind == "semantic_replay_behavior_mismatch":
        subtype = "behavior_mismatch_under_import_harness"
    return {
        "subtype": subtype,
        "blocker_kind": blocker_kind,
        "required_input_signature": ",".join(required),
        "target_replay_risk": _candidate_effective_replay_risk(root, row),
        "module_replay_risk": _candidate_replay_risk(root, row),
        "direct_file_preferred": _prefer_direct_file_replay(root, row),
        "has_attribute_base_class_definition": "attribute_base_class_definition" in fact_tags,
        "has_target_self_attribute_gap": "target_self_attribute_read_without_assignment" in fact_tags,
        "missing_import": missing_import,
        "missing_import_kind": missing_import_kind,
    }


def _import_isolation_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = [
        dict(case.get("import_isolation_profile") or {})
        for case in cases
        if case.get("next_operator_lane") == "import_dependency_isolation_candidate"
        and isinstance(case.get("import_isolation_profile"), dict)
    ]
    subtype_counter: Counter[str] = Counter()
    blocker_counter: Counter[str] = Counter()
    missing_import_counter: Counter[str] = Counter()
    missing_import_kind_counter: Counter[str] = Counter()
    signature_counter: Counter[str] = Counter()
    for profile in profiles:
        subtype_counter[str(profile.get("subtype") or "unknown")] += 1
        blocker_counter[str(profile.get("blocker_kind") or "unknown")] += 1
        if profile.get("missing_import"):
            missing_import_counter[str(profile.get("missing_import"))] += 1
            missing_import_kind_counter[str(profile.get("missing_import_kind") or "unknown")] += 1
        signature_counter[str(profile.get("required_input_signature") or "")] += 1
    return {
        "case_count": len(profiles),
        "subtype_summary": dict(sorted(subtype_counter.items())),
        "blocker_summary": dict(sorted(blocker_counter.items())),
        "direct_file_preferred_count": sum(
            1 for profile in profiles if profile.get("direct_file_preferred") is True
        ),
        "attribute_base_metaclass_risk_count": sum(
            1 for profile in profiles if profile.get("has_attribute_base_class_definition") is True
        ),
        "target_self_attribute_gap_count": sum(
            1 for profile in profiles if profile.get("has_target_self_attribute_gap") is True
        ),
        "missing_import_kind_summary": dict(sorted(missing_import_kind_counter.items())),
        "top_missing_imports": _top(missing_import_counter, 12),
        "top_required_input_signatures": _top(signature_counter, 8),
    }


def _missing_import_from_error(error_text: str) -> str:
    if not error_text:
        return ""
    patterns = [
        r"ModuleNotFoundError: No module named '([^']+)'",
        r'No module named "([^"]+)"',
        r"ImportError: cannot import name '([^']+)' from '([^']+)'",
        r"DistributionNotFound: The '([^']+)' distribution was not found",
        r"pkg_resources\.DistributionNotFound: The '([^']+)' distribution was not found",
    ]
    for pattern in patterns:
        match = re.search(pattern, error_text)
        if not match:
            continue
        if len(match.groups()) == 2:
            return f"{match.group(2)}:{match.group(1)}"
        return match.group(1)
    return ""


def _missing_import_kind(workspace_root: Path, row: dict[str, Any], missing_import: str) -> str:
    if not missing_import:
        return "unknown"
    module, _, symbol = missing_import.partition(":")
    import_root = module.split(".", 1)[0]
    stdlib_modules = getattr(sys, "stdlib_module_names", set())
    if module in {"types", "enum", "typing", "builtins"} and symbol:
        return "stdlib_symbol_compat"
    if import_root in stdlib_modules:
        return "stdlib_module_compat"
    project_root = workspace_root / str(row.get("project_root") or "")
    target_parts = Path(str(row.get("path") or "")).parts
    if (
        import_root in target_parts
        or (project_root / import_root).exists()
        or (project_root / f"{import_root}.py").exists()
    ):
        return "project_local_dependency"
    if "." in module:
        return "external_or_project_dependency"
    return "external_dependency"
