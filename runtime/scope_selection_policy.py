"""Config-backed scope selection helpers for foundation roles."""

from __future__ import annotations

from typing import Any

from runtime.source_target_policy import scope_policy_int, scope_policy_list


PREFERRED_SCOPE_ROOTS = set(scope_policy_list("preferred_roots"))
CORE_SCOPE_ROOT_TOKENS = tuple(scope_policy_list("core_root_tokens"))
SUPPORT_SCOPE_ROOTS = set(scope_policy_list("support_roots"))
SUPPORT_SCOPE_SUFFIXES = tuple(scope_policy_list("support_root_suffixes"))
DISFAVORED_SCOPE_ROOTS = set(scope_policy_list("disfavored_roots"))
SOFT_DISFAVORED_SCOPE_ROOTS = set(scope_policy_list("soft_disfavored_roots"))
SYNTAX_FIXTURE_PARTS = set(scope_policy_list("syntax_fixture_path_parts"))
SYNTAX_FIXTURE_ROOTS = set(scope_policy_list("syntax_fixture_roots"))
SYNTAX_FIXTURE_DATA_ROOTS = tuple(scope_policy_list("syntax_fixture_data_roots"))
SYNTAX_FIXTURE_DATA_TOKENS = scope_policy_list("syntax_fixture_data_path_tokens")
SYNTAX_FIXTURE_DOC_TOKENS = scope_policy_list("syntax_fixture_doc_path_tokens")
SYNTAX_FIXTURE_DOC_REQUIRED = scope_policy_list("syntax_fixture_doc_required_any")
SYNTAX_FIXTURE_FILE_TOKENS = scope_policy_list("syntax_fixture_file_tokens")
CANDIDATE_NOISE_PARTS = set(scope_policy_list("candidate_noise_parts"))
CANDIDATE_NOISE_SUFFIXES = tuple(scope_policy_list("candidate_noise_suffixes"))
PATH_SCORE_ROOTS = set(scope_policy_list("path_score_roots"))
MONOREPO_PYTHON_ROOTS = set(scope_policy_list("monorepo_python_roots"))
ALIASED_CORE_SUFFIXES = tuple(scope_policy_list("aliased_core_suffixes"))


def syntax_error_fixture_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    first = lowered.strip("/").split("/", 1)[0]
    fixture_parts = {part for part in lowered.split("/") if part in SYNTAX_FIXTURE_PARTS}
    wrapped = f"/{lowered}"
    example_doc = any(token in wrapped for token in SYNTAX_FIXTURE_DOC_TOKENS) and any(
        token in wrapped for token in SYNTAX_FIXTURE_DOC_REQUIRED
    )
    test_data = any(token in wrapped for token in SYNTAX_FIXTURE_DATA_TOKENS) and lowered.startswith(
        SYNTAX_FIXTURE_DATA_ROOTS
    )
    test_support_file = first in SYNTAX_FIXTURE_ROOTS
    template_file = any(token in lowered for token in SYNTAX_FIXTURE_FILE_TOKENS)
    return bool(fixture_parts) or test_support_file or test_data or example_doc or template_file


def syntax_damage_is_quarantinable(project_report: dict[str, Any]) -> bool:
    source_health = dict(project_report.get("source_health") or {})
    if source_health.get("status") != "damaged" or int(source_health.get("inaccessible_count") or 0) > 0:
        return False
    samples = [dict(row) for row in source_health.get("syntax_error_samples", []) if isinstance(row, dict)]
    count = int(source_health.get("syntax_error_count") or 0)
    if not count or count > len(samples) or count > scope_policy_int("quarantinable_production_syntax_error_max", 0):
        return False
    damaged = {str(row.get("path") or "").replace("\\", "/") for row in samples}
    answers = dict(project_report.get("answers") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    candidates = [dict(row) for row in plan.get("capabilities_to_extract", []) if isinstance(row, dict)]
    safe = [
        row for row in candidates
        if not any(str(row.get("source") or row.get("capability") or "").startswith(f"{path}:") for path in damaged)
    ]
    return len(safe) >= scope_policy_int("quarantine_min_safe_candidates", 3)


def scope_candidate_priority(rel_path: str) -> int:
    lowered = rel_path.replace("\\", "/").lower().strip("/")
    first = lowered.split("/", 1)[0]
    priority = 0
    if first in PREFERRED_SCOPE_ROOTS:
        priority += scope_policy_int("preferred_root_bonus", 40)
    if any(token in first for token in CORE_SCOPE_ROOT_TOKENS):
        priority += scope_policy_int("core_root_bonus", 25)
    if first.endswith(SUPPORT_SCOPE_SUFFIXES) or first in SUPPORT_SCOPE_ROOTS:
        priority -= scope_policy_int("support_root_penalty", 15)
    if disfavored_scope_root(rel_path):
        priority -= scope_policy_int("disfavored_root_penalty", 80)
    return priority


def scope_path_score(rel_path: str, *, root_name: str, parent_name: str) -> int:
    lowered = rel_path.replace("\\", "/").lower().strip("/")
    first = lowered.split("/", 1)[0]
    normalized_root = root_name.lower().replace("-", "_")
    normalized_parent = parent_name.lower().replace("-", "_")
    normalized_first = first.replace("-", "_")
    score = 0
    if first in PATH_SCORE_ROOTS:
        score += scope_policy_int("path_score_root_bonus", 35)
    if normalized_first == normalized_root:
        score += scope_policy_int("path_score_project_name_bonus", 35)
    if normalized_parent and normalized_first == normalized_parent:
        score += scope_policy_int("path_score_parent_name_bonus", 45)
    elif normalized_first.startswith(f"{normalized_root}_") or normalized_first.startswith(f"{normalized_root}-"):
        score += scope_policy_int("path_score_project_prefix_bonus", 25)
    elif normalized_root and normalized_root in normalized_first and any(token in normalized_first for token in ("core", "sdk")):
        score += scope_policy_int("path_score_core_alias_bonus", 22)
    if first in DISFAVORED_SCOPE_ROOTS:
        score -= 50
    elif first in SOFT_DISFAVORED_SCOPE_ROOTS:
        score -= scope_policy_int("soft_disfavored_root_penalty", 25)
    return score


def disfavored_scope_root(path: str) -> bool:
    first = path.replace("\\", "/").lower().strip("/").split("/", 1)[0]
    return first in DISFAVORED_SCOPE_ROOTS


def candidate_noise_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    parts = [part for part in lowered.split("/") if part]
    if any(part in CANDIDATE_NOISE_PARTS for part in parts):
        return True
    return lowered.endswith(CANDIDATE_NOISE_SUFFIXES)


def scope_candidate_kind(py_count: int, js_ts_count: int, manifest_hits: list[str]) -> str:
    has_package = any(path.endswith("package.json") for path in manifest_hits)
    has_python = py_count > 0
    if has_python and has_package:
        return "mixed_python_frontend_candidate"
    if has_python:
        return "python_project_candidate"
    if js_ts_count or has_package:
        return "frontend_or_extension_candidate"
    return "artifact_or_unknown_candidate"


def scope_thresholds() -> dict[str, Any]:
    return {
        "aliased_core_suffixes": ALIASED_CORE_SUFFIXES,
        "disfavored_roots": DISFAVORED_SCOPE_ROOTS,
        "monorepo_python_roots": MONOREPO_PYTHON_ROOTS,
        "preferred_roots": PREFERRED_SCOPE_ROOTS,
        "soft_disfavored_roots": SOFT_DISFAVORED_SCOPE_ROOTS,
    }
