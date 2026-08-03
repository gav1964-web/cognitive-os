"""Ranking helpers for SpecWriter extraction contracts."""

from __future__ import annotations

from typing import Any

from .contract_archetype_inference import archetype_ranking_adjustments
from .semantic_target_profiles import semantic_ranking_adjustments
from .target_quality_policy import nested_policy_tokens, policy_tokens, target_quality_section


SPEC_WRITER_POLICY = target_quality_section("spec_writer_ranking")
DETERMINISTIC_SHAPE_TOKENS = policy_tokens(SPEC_WRITER_POLICY, "deterministic_shape_tokens")
FRAMEWORK_BOUNDARY_TOKENS = policy_tokens(SPEC_WRITER_POLICY, "framework_boundary_tokens")
HANDLER_BOUNDARY_TOKENS = policy_tokens(SPEC_WRITER_POLICY, "handler_boundary_tokens")
REPAIR_CONTROL_SURFACE_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "repair_loop", "control_surface_path_tokens")
REPAIR_LLM_HYPOTHESIS_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "repair_loop", "llm_hypothesis_symbols"))
REPAIR_MODULE_VALIDATION_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "repair_loop", "module_validation_symbols"))
REPAIR_GOAL_TO_SPEC_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "repair_loop", "goal_to_spec_symbols"))
REPAIR_ORCHESTRATION_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "repair_loop", "orchestration_symbols"))
REPAIR_GENERATED_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "repair_loop", "generated_path_tokens")
OPERATIONAL_API_PATH_SUFFIXES = nested_policy_tokens(SPEC_WRITER_POLICY, "operational_boundary", "api_path_suffixes")
OPERATIONAL_API_RUNTIME_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "operational_boundary", "api_runtime_symbols"))
OPERATIONAL_DISPATCHER_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "operational_boundary", "dispatcher_symbols"))
OPERATIONAL_CONTROL_SYMBOL_CONTAINS_ANY = nested_policy_tokens(
    SPEC_WRITER_POLICY, "operational_boundary", "control_symbol_contains_any"
)
OPERATIONAL_LIFECYCLE_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "operational_boundary", "lifecycle_symbols"))
OPERATIONAL_LIFECYCLE_SUFFIXES = nested_policy_tokens(SPEC_WRITER_POLICY, "operational_boundary", "lifecycle_suffixes")
OPERATIONAL_ENVIRONMENT_COUPLING_TOKENS = nested_policy_tokens(
    SPEC_WRITER_POLICY, "operational_boundary", "environment_coupling_tokens"
)
OPERATIONAL_DATA_SHAPE_SYMBOL_TOKENS = nested_policy_tokens(
    SPEC_WRITER_POLICY, "operational_boundary", "data_shape_symbol_tokens"
)
DOMAIN_QUERY_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "query_symbols"))
DOMAIN_QUERY_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "query_path_tokens")
DOMAIN_QUERY_SYMBOL_CONTAINS_ANY = nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "query_symbol_contains_any")
DOMAIN_QUERY_MODULE_PATH_TOKEN = str(
    dict(SPEC_WRITER_POLICY.get("domain_contract") or {}).get("query_module_path_token") or ""
).lower()
DOMAIN_QUERY_MODULE_EXCLUDED_SYMBOLS = set(
    nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "query_module_excluded_symbols")
)
DOMAIN_WEAK_ACCESSOR_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "weak_accessor_symbols"))
DOMAIN_STORAGE_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "storage_path_tokens")
DOMAIN_MIDDLEWARE_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "domain_contract", "middleware_path_tokens")
REPRESENTATIVE_FLOW_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "representative_slice", "flow_tokens")
REPRESENTATIVE_UTILITY_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "representative_slice", "utility_tokens")
REPRESENTATIVE_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "representative_slice", "representative_path_tokens")
REPRESENTATIVE_UTILITY_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "representative_slice", "utility_path_tokens")
AD_HOC_EVALUATOR_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "representative_slice", "ad_hoc_evaluator_symbols"))
AD_HOC_EVALUATOR_PATH_TOKENS = nested_policy_tokens(
    SPEC_WRITER_POLICY, "representative_slice", "ad_hoc_evaluator_path_tokens"
)
EXEC_READY_SYMBOL_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "executable_readiness", "first_slice_symbol_tokens")
EXEC_READY_SIMPLE_ANNOTATIONS = nested_policy_tokens(SPEC_WRITER_POLICY, "executable_readiness", "simple_input_annotations")
EXEC_READY_HARD_SYMBOL_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "executable_readiness", "hard_runtime_symbol_tokens")
EXEC_READY_HARD_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "executable_readiness", "hard_runtime_path_tokens")
TRIVIAL_HELPER_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "trivial_helper", "symbols"))
TRIVIAL_HELPER_SYMBOL_CONTAINS_ANY = nested_policy_tokens(SPEC_WRITER_POLICY, "trivial_helper", "symbol_contains_any")
TRIVIAL_HELPER_SUFFIXES = nested_policy_tokens(SPEC_WRITER_POLICY, "trivial_helper", "suffixes")
TRIVIAL_HELPER_SUFFIX_ALLOWED_CONTAINS_ANY = nested_policy_tokens(
    SPEC_WRITER_POLICY, "trivial_helper", "suffix_allowed_contains_any"
)
TRIVIAL_HELPER_PREFIXES = nested_policy_tokens(SPEC_WRITER_POLICY, "trivial_helper", "prefixes")
LIVENESS_PROBE_SYMBOLS = set(policy_tokens(SPEC_WRITER_POLICY, "liveness_probe_symbols"))
BOOTSTRAP_SUPPORT_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "bootstrap_support", "symbols"))
BOOTSTRAP_SUPPORT_ARG_PATH_TOKENS = nested_policy_tokens(SPEC_WRITER_POLICY, "bootstrap_support", "arg_path_tokens")
LOW_VALUE_PATH_SUFFIXES = nested_policy_tokens(SPEC_WRITER_POLICY, "low_value_first_slice", "path_suffixes")
LOW_VALUE_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "low_value_first_slice", "symbols"))
MUTATION_LIKE_SYMBOLS = set(nested_policy_tokens(SPEC_WRITER_POLICY, "mutation_like_first_slice", "symbols"))
MUTATION_LIKE_PREFIXES = nested_policy_tokens(SPEC_WRITER_POLICY, "mutation_like_first_slice", "prefixes")


def name_and_contract_score(source: str, signature: dict[str, Any], side_effects: list[str]) -> tuple[int, list[str]]:
    lowered = source.lower()
    args = [str(arg.get("annotation") or "") for arg in list(signature.get("args", []) or []) if isinstance(arg, dict)]
    text = " ".join([lowered, *args]).lower()
    score = 0
    reasons: list[str] = []
    if any(token in lowered for token in DETERMINISTIC_SHAPE_TOKENS):
        score += 16
        reasons.append("deterministic parser/normalizer/validator shape")
    domain_score, domain_reasons = _domain_contract_score(lowered)
    score += domain_score
    reasons.extend(domain_reasons)
    repair_score, repair_reasons = _repair_loop_contract_score(lowered)
    score += repair_score
    reasons.extend(repair_reasons)
    representative_score, representative_reasons = _representative_slice_score(lowered)
    score += representative_score
    reasons.extend(representative_reasons)
    readiness_score, readiness_reasons = _executable_readiness_score(lowered, signature, side_effects)
    score += readiness_score
    reasons.extend(readiness_reasons)
    if _is_trivial_helper_source(lowered):
        score -= 30
        reasons.append("small helper is less representative than a flow-level capability")
    if _is_liveness_probe_source(lowered):
        score -= 35
        reasons.append("health/status/ping probe is liveness evidence, not first reusable domain contract")
    if _is_bootstrap_support_source(lowered):
        score -= 55
        reasons.append("CLI/bootstrap support helper is evidence, not first architectural slice")
    if _is_low_value_first_slice_source(lowered):
        score -= 45
        reasons.append("constructor/logging/config helper is evidence, not first implementation target")
    if _is_mutation_like_first_slice_source(lowered):
        score -= 35
        reasons.append("write/update/delete operation is side-effect evidence, not first reusable contract")
    if "memory_state" in side_effects:
        score -= 35
        reasons.append("explicit memory/global state mutation")
    if any(token in text for token in FRAMEWORK_BOUNDARY_TOKENS):
        score -= 35
        reasons.append("framework request/response boundary, not first reusable core contract")
    if any(token in lowered for token in HANDLER_BOUNDARY_TOKENS):
        score -= 20
        reasons.append("handler/middleware boundary is less reusable than a core helper")
    return score, reasons


def _executable_readiness_score(lowered_source: str, signature: dict[str, Any], side_effects: list[str]) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    if side_effects:
        return 0, []
    if any(token in lowered_source for token in REPRESENTATIVE_FLOW_TOKENS) or any(
        token in path for token in REPAIR_CONTROL_SURFACE_PATH_TOKENS
    ):
        return 0, []
    args = [arg for arg in list(signature.get("args", []) or []) if isinstance(arg, dict)]
    annotations = " ".join(str(arg.get("annotation") or "") for arg in args).lower()
    score = 0
    reasons: list[str] = []
    if any(token in symbol for token in EXEC_READY_SYMBOL_TOKENS):
        score += 10
        reasons.append("first executable slice has parser/normalizer/builder shape")
    if args and all(any(token in str(arg.get("annotation") or "").lower() for token in EXEC_READY_SIMPLE_ANNOTATIONS) for arg in args):
        score += 4
        reasons.append("inputs look materializable by executable acceptance fixtures")
    if any(token in symbol or token in annotations for token in EXEC_READY_HARD_SYMBOL_TOKENS) or any(
        token in path for token in EXEC_READY_HARD_PATH_TOKENS
    ):
        score -= 28
        reasons.append("runtime object boundary is weaker as first executable contract")
    return score, reasons


def _repair_loop_contract_score(lowered_source: str) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    text = f"{path}:{symbol}"
    score = 0
    reasons: list[str] = []
    if any(token in text for token in REPAIR_CONTROL_SURFACE_PATH_TOKENS):
        score += 18
        reasons.append("source belongs to LLM auto-repair control surface")
    if symbol in REPAIR_LLM_HYPOTHESIS_SYMBOLS:
        score += 44
        reasons.append("LLM hypothesis boundary is central to repair-attempt contract")
    if symbol in REPAIR_MODULE_VALIDATION_SYMBOLS:
        score += 38
        reasons.append("module contract checker is a strong validation boundary")
    if symbol in REPAIR_GOAL_TO_SPEC_SYMBOLS:
        score += 30
        reasons.append("goal-to-spec transform is a useful planning contract boundary")
    if symbol in REPAIR_ORCHESTRATION_SYMBOLS:
        score += 22
        reasons.append("repair orchestration loop is representative but needs bounded subcontracts")
    if any(token in path for token in REPAIR_GENERATED_PATH_TOKENS):
        score -= 70
        reasons.append("generated project output is evidence, not first source transformation target")
    return score, reasons


def candidate_level_bonus(level: str) -> int:
    return {
        "core_flow": 12,
        "boundary": 8,
        "broad_split": 5,
        "preferred_anchor": 4,
        "helper_transform": 2,
    }.get(level, 0)


def operational_boundary_score(source: str, signature: dict[str, Any], claims: list[str]) -> tuple[int, list[str]]:
    lowered = source.lower()
    symbol = lowered.rsplit(":", 1)[-1]
    path = lowered.split(":", 1)[0]
    args = " ".join(str(arg.get("name") or "") for arg in list(signature.get("args", []) or []) if isinstance(arg, dict))
    text = " ".join([lowered, symbol, args, *claims]).lower()
    score = 0
    reasons: list[str] = []
    if path.endswith(OPERATIONAL_API_PATH_SUFFIXES) or symbol in OPERATIONAL_API_RUNTIME_SYMBOLS:
        score -= 25
        reasons.append("API/runtime boundary should not outrank core capability candidates")
    if symbol in OPERATIONAL_DISPATCHER_SYMBOLS:
        score -= 40
        reasons.append("request dispatcher boundary is evidence, not first reusable core contract")
    if any(token in symbol for token in OPERATIONAL_CONTROL_SYMBOL_CONTAINS_ANY):
        score -= 25
        reasons.append("operational control function is less reusable as first extraction")
    if symbol in OPERATIONAL_LIFECYCLE_SYMBOLS or symbol.endswith(OPERATIONAL_LIFECYCLE_SUFFIXES):
        score -= 30
        reasons.append("operational lifecycle/mutation wrapper needs a narrower contract target")
    if any(token in text for token in OPERATIONAL_ENVIRONMENT_COUPLING_TOKENS):
        score -= 15
        reasons.append("runtime environment coupling needs later isolation review")
    if any(token in symbol for token in OPERATIONAL_DATA_SHAPE_SYMBOL_TOKENS):
        score += 10
        reasons.append("bounded data-shaping helper is a better extraction target")
    return score, reasons


def _domain_contract_score(lowered_source: str) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    score = 0
    reasons: list[str] = []
    query_path = any(token in path for token in DOMAIN_QUERY_PATH_TOKENS)
    if (
        symbol in DOMAIN_QUERY_SYMBOLS
        or (query_path and symbol == "evaluate")
        or any(token in symbol for token in DOMAIN_QUERY_SYMBOL_CONTAINS_ANY)
    ):
        score += 28
        reasons.append("query/condition contract is a strong database first-slice target")
    if DOMAIN_QUERY_MODULE_PATH_TOKEN in path and symbol not in DOMAIN_QUERY_MODULE_EXCLUDED_SYMBOLS:
        score += 18
        reasons.append("database query module is closer to reusable contract boundary")
    if symbol in DOMAIN_WEAK_ACCESSOR_SYMBOLS:
        score -= 18
        reasons.append("generic accessor is weaker than query/condition contract")
    if any(token in path for token in DOMAIN_STORAGE_PATH_TOKENS):
        score -= 18
        reasons.append("storage adapter is persistence evidence, not first domain contract")
    if any(token in path for token in DOMAIN_MIDDLEWARE_PATH_TOKENS):
        score -= 12
        reasons.append("middleware adapter is operational evidence, not first domain contract")
    return score, reasons


def _representative_slice_score(lowered_source: str) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    text = f"{path}:{symbol}"
    score = 0
    reasons: list[str] = []
    if any(token in text for token in REPRESENTATIVE_FLOW_TOKENS):
        score += 28
        reasons.append("representative domain flow/lifecycle slice")
    if any(token in text for token in REPRESENTATIVE_UTILITY_TOKENS):
        score -= 24
        reasons.append("domain utility/helper is less representative than lifecycle flow")
    if any(token in path for token in REPRESENTATIVE_PATH_TOKENS):
        score += 12
        reasons.append("source path belongs to representative domain subsystem")
    if any(token in path for token in REPRESENTATIVE_UTILITY_PATH_TOKENS):
        score -= 12
        reasons.append("source path looks like utility/support surface")
    profile_adjustments = semantic_ranking_adjustments(f"{path}:{symbol}")
    archetype_adjustments = archetype_ranking_adjustments(f"{path}:{symbol}")
    score += int(profile_adjustments["score_delta"])
    score += int(archetype_adjustments["score_delta"])
    reasons.extend(profile_adjustments["reasons"])
    reasons.extend(archetype_adjustments["reasons"])
    if symbol in AD_HOC_EVALUATOR_SYMBOLS and any(token in path for token in AD_HOC_EVALUATOR_PATH_TOKENS):
        score -= 30
        reasons.append("ad-hoc evaluator is less stable than generation/postprocessing contract")
    return score, reasons


def _is_trivial_helper_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    if symbol in TRIVIAL_HELPER_SYMBOLS:
        return True
    if any(token in symbol for token in TRIVIAL_HELPER_SYMBOL_CONTAINS_ANY):
        return True
    if symbol.endswith(TRIVIAL_HELPER_SUFFIXES) and not any(
        token in symbol for token in TRIVIAL_HELPER_SUFFIX_ALLOWED_CONTAINS_ANY
    ):
        return True
    if symbol.startswith(TRIVIAL_HELPER_PREFIXES):
        return True
    return False


def _is_liveness_probe_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    return symbol in LIVENESS_PROBE_SYMBOLS


def _is_bootstrap_support_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    if symbol in BOOTSTRAP_SUPPORT_SYMBOLS:
        return True
    if symbol.endswith("_args") and any(token in path for token in BOOTSTRAP_SUPPORT_ARG_PATH_TOKENS):
        return True
    return False


def _is_low_value_first_slice_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    if symbol in LOW_VALUE_SYMBOLS or path.endswith(LOW_VALUE_PATH_SUFFIXES):
        return True
    return False


def _is_mutation_like_first_slice_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    if symbol in MUTATION_LIKE_SYMBOLS:
        return True
    return symbol.startswith(MUTATION_LIKE_PREFIXES)
