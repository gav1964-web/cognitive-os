"""Evidence-derived refinements for candidate-selection admission."""

from __future__ import annotations

import json
from typing import Any


def policy_signature(policy: dict[str, Any]) -> str:
    return json.dumps({
        "trigger_signals": policy["trigger_signals"],
        "structural_requirements": policy["structural_requirements"],
        "preflight_trigger_requirements": policy["preflight_trigger_requirements"],
        "candidate_ordering": policy.get("candidate_ordering"),
    }, sort_keys=True, separators=(",", ":"))


def portable_execution_discriminators(
    failed: list[dict[str, Any]], successful: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    removed_costs = [
        set(row.get("execution_cost_rules") or [])
        - set(success.get("execution_cost_rules") or [])
        for row, success in zip(failed, successful)
    ]
    costs = set.intersection(*removed_costs) if removed_costs else set()
    failed_dependencies = {
        str(row["dependency_status"]) for row in failed if row.get("dependency_status")
    }
    successful_dependencies = {
        str(row["dependency_status"]) for row in successful if row.get("dependency_status")
    }
    dependencies = (
        failed_dependencies - successful_dependencies
        if successful and len(successful_dependencies) == len(successful)
        else set()
    )
    requirements = {}
    preflight = {}
    if costs:
        requirements["forbidden_ranking_reason_tokens"] = sorted(costs)
        preflight["any_ranking_reason_tokens"] = sorted(costs)
    if dependencies:
        requirements["forbidden_dependency_status"] = sorted(dependencies)
        preflight["dependency_status"] = sorted(dependencies)
    return requirements, preflight


def refine_preflight(
    policy: dict[str, Any], effect: dict[str, Any], regressions: list[dict[str, Any]]
) -> dict[str, Any]:
    holdout = dict(effect.get("control", {}).get("selected_candidate_quality") or {})
    holdout_effects = set(
        dict(holdout.get("structural_evidence") or {}).get("observed_side_effects") or []
    )
    regression_effects = {
        str(value) for row in regressions
        for value in dict(
            dict(row.get("selected_candidate_quality") or {}).get("structural_evidence") or {}
        ).get("observed_side_effects") or []
    }
    extra = sorted(regression_effects - holdout_effects)
    trigger = dict(policy.get("preflight_trigger_requirements") or {})
    common = dict(trigger.get("common_requirements") or {})
    if extra:
        common["forbidden_observed_side_effects"] = sorted({
            *[str(value) for value in common.get("forbidden_observed_side_effects") or []], *extra,
        })
    holdout_dependency = _dependency_status(holdout)
    regression_dependencies = {
        _dependency_status(dict(row.get("selected_candidate_quality") or {}))
        for row in regressions
    }
    if holdout_dependency and holdout_dependency not in regression_dependencies:
        common["dependency_status"] = [holdout_dependency]
    holdout_shape = dict(holdout.get("structural_evidence") or {})
    holdout_args = int(holdout_shape.get("argument_count") or 0)
    regression_args = [
        int(dict(dict(row.get("selected_candidate_quality") or {}).get("structural_evidence") or {}).get(
            "argument_count"
        ) or 0)
        for row in regressions
    ]
    if holdout_args and regression_args and holdout_args > max(regression_args):
        common["min_argument_count"] = holdout_args
    if common:
        trigger["common_requirements"] = common
    if trigger == dict(policy.get("preflight_trigger_requirements") or {}):
        return {}
    return {**policy, "preflight_trigger_requirements": trigger}


def refine_reproduction(
    policy: dict[str, Any], effect: dict[str, Any], reproduction: dict[str, Any]
) -> dict[str, Any]:
    expected = dict(effect.get("treatment", {}).get("selected_candidate_quality") or {})
    actual = dict(reproduction.get("selected_candidate_quality") or {})
    extra = sorted(_execution_cost_rules(actual) - _execution_cost_rules(expected))
    required = dict(policy.get("structural_requirements") or {})
    trigger = dict(policy.get("preflight_trigger_requirements") or {})
    if extra:
        required["forbidden_ranking_reason_tokens"] = sorted({
            *[str(value) for value in required.get("forbidden_ranking_reason_tokens") or []], *extra,
        })
        trigger = _add_trigger_alternative(trigger, {
            "any_ranking_reason_tokens": extra,
        })
    expected_dependency = _dependency_status(expected)
    actual_dependency = _dependency_status(actual)
    if expected_dependency and actual_dependency and actual_dependency != expected_dependency:
        required["forbidden_dependency_status"] = sorted({
            *[str(value) for value in required.get("forbidden_dependency_status") or []],
            actual_dependency,
        })
        trigger = _add_trigger_alternative(trigger, {
            "dependency_status": [actual_dependency],
        })
    expected_shape = dict(expected.get("structural_evidence") or {})
    actual_shape = dict(actual.get("structural_evidence") or {})
    if (
        int(expected_shape.get("argument_count") or 0) >= 1
        and int(actual_shape.get("argument_count") or 0) == 0
    ):
        required["min_argument_count"] = max(1, int(required.get("min_argument_count") or 0))
        trigger = _add_trigger_alternative(trigger, {"max_argument_count": 0})
    expected_usage = len(dict(expected_shape.get("argument_usage_types") or {}))
    actual_usage = len(dict(actual_shape.get("argument_usage_types") or {}))
    if expected_usage > actual_usage:
        required["min_argument_usage_count"] = max(
            expected_usage, int(required.get("min_argument_usage_count") or 0),
        )
        trigger = _add_trigger_alternative(trigger, {
            "max_argument_usage_count": actual_usage,
        })
    if (
        int(expected_shape.get("return_paths") or 0) >= 1
        and int(actual_shape.get("return_paths") or 0) == 0
    ):
        required["min_return_paths"] = max(1, int(required.get("min_return_paths") or 0))
        basis = str(actual_shape.get("output_inference_basis") or "")
        if basis:
            trigger = _add_trigger_alternative(trigger, {
                "output_inference_basis": [basis],
            })
    if required == dict(policy.get("structural_requirements") or {}):
        return {}
    return {
        **policy,
        "structural_requirements": required,
        "preflight_trigger_requirements": trigger,
    }


def _add_trigger_alternative(
    trigger: dict[str, Any], alternative: dict[str, Any]
) -> dict[str, Any]:
    alternatives = list(trigger.get("alternatives") or [])
    common = dict(trigger.get("common_requirements") or {})
    base = {
        key: value for key, value in trigger.items()
        if key not in {"alternatives", "common_requirements"}
    }
    if base:
        alternatives.insert(0, base)
    encoded = {repr(sorted(dict(row).items())) for row in alternatives}
    if repr(sorted(alternative.items())) not in encoded:
        alternatives.append(alternative)
    return {**({"common_requirements": common} if common else {}), "alternatives": alternatives}


def _execution_cost_rules(quality: dict[str, Any]) -> set[str]:
    selection = dict(quality.get("selection_evidence") or {})
    prefix = "execution cost requires reselection:"
    rules = set()
    for reason in selection.get("ranking_reasons") or []:
        text = str(reason).strip()
        if text.lower().startswith(prefix):
            rules.update(part.strip() for part in text[len(prefix):].split(",") if part.strip())
    return rules


def _dependency_status(quality: dict[str, Any]) -> str:
    selection = dict(quality.get("selection_evidence") or {})
    return str(dict(selection.get("dependency_readiness") or {}).get("status") or "")
