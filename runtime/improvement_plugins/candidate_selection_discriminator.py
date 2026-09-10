"""Discover a measured candidate-selection challenger through bounded shadow trials."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    packet = dict(context.get("failure_packet") or {})
    diagnosis = dict(context.get("diagnosis") or {})
    config = dict(context.get("plugin_config") or {})
    failure_class = str(diagnosis.get("failure_class") or "unknown")
    supported = {str(value) for value in config.get("failure_classes") or []}
    if supported and failure_class not in supported:
        return {"status": "not_applicable", "reason": "failure_class_not_supported"}
    source = _canonical_target(packet.get("selected_candidate"))
    if not source:
        return {"status": "not_applicable", "reason": "selected_candidate_missing"}
    candidates, prior_trace = _candidate_sources_with_prior(
        Path(context["root"]), Path(context["project_dir"]),
        packet, diagnosis, source, config,
    )
    if not candidates:
        return {"status": "blocked", "reason": "bounded_challenger_pool_empty"}
    control = _control(packet)
    trials = [
        _trial(Path(context["root"]), Path(context["project_dir"]), control, candidate)
        for candidate in candidates
    ]
    confirmed = [row for row in trials if row["status"] == "confirmed_selection_effect"]
    if not confirmed:
        convergent = _convergent_effect(trials, source, config)
        if convergent:
            trials.append(convergent)
            confirmed.append(convergent)
    if not confirmed:
        return {
            "status": "blocked",
            "reason": "shadow_discriminator_not_confirmed",
            "tested_challenger_count": len(trials),
            "trials": [_trial_summary(row) for row in trials],
        }
    best = sorted(confirmed, key=lambda row: (-float(row["score_delta"]), row["challenger"]))[0]
    return {
        "status": "trial_passed",
        "change_type": "foundation_selection_contrast",
        "selected_challenger": best["challenger"],
        "promotion_applied": False,
        "implements_capability": "candidate_selection_discriminator_plugin",
        "implements_capabilities": list(config.get("implements_capabilities") or []),
        "shadow_prior": prior_trace,
        "evolution": {
            "status": "passed",
            "decision": "shadow_challenger_confirmed",
            "baseline": control,
            "shadow": best["treatment"],
            "promotion": {"applied": False, "reason": "contrast_staging_required"},
            "gates": {
                "bounded_existing_candidates": True,
                "positive_score_delta": True,
                "no_role_regression": True,
                "executable_acceptance": True,
                "source_project_unchanged": True,
            },
        },
        "trials": [_trial_summary(row) for row in trials],
    }


def _candidate_sources(
    packet: dict[str, Any], diagnosis: dict[str, Any], source: str, config: dict[str, Any]
) -> list[str]:
    evidence = dict(packet.get("artifact_evidence") or {})
    spec = dict(evidence.get("technical_spec") or {})
    adr = dict(evidence.get("architecture_decision") or {})
    clamp = dict(adr.get("evaluation_target_clamp") or {})
    ranked = [dict(row) for row in list(spec.get("ranked_candidates") or []) if isinstance(row, dict)]
    reselection = dict(spec.get("reselection") or {})
    blocked_sources = {
        _canonical_target(row.get("source"))
        for row in ranked
        if _candidate_trial_blocked(row)
    }
    ranked_sources = [
        _canonical_target(row.get("source"))
        for row in sorted(ranked, key=_candidate_rank)
        if str(row.get("source") or "") not in blocked_sources
    ]
    selected_targets = [_canonical_target(value) for value in reselection.get("selected_targets") or []]
    first_slice_targets = [
        _canonical_target(value) for value in dict(adr.get("first_slice") or {}).get("targets") or []
    ]
    clamped_candidates = [_canonical_target(value) for value in clamp.get("candidate_pool") or []]
    source_candidates = [_canonical_target(value) for value in adr.get("source_candidate_pool") or []]
    recovery_candidates = [_canonical_target(value) for value in packet.get("retrieval_recovery_candidates") or []]
    eligible = set(
        ranked_sources + selected_targets + first_slice_targets + clamped_candidates
        + source_candidates + recovery_candidates
    )
    values = [_canonical_target(diagnosis.get("recommended_source"))]
    values.extend(value for value in recovery_candidates if ":" in value)
    values.extend(value for value in source_candidates if ":" in value)
    values.extend(value for value in ranked_sources if ":" in value)
    values.extend(value for value in selected_targets if ":" in value)
    values.extend(value for value in first_slice_targets if ":" in value)
    values.extend(value for value in clamped_candidates if ":" in value)
    values.extend(value for value in ranked_sources if ":" not in value)
    maximum = max(1, int(config.get("maximum_shadow_challengers") or 4))
    bounded = list(dict.fromkeys(
        value for value in values
        if value and value != source and value in eligible and value not in blocked_sources
    ))
    return _diverse_candidates(bounded, maximum)


def _candidate_sources_with_prior(
    root: Path, project_dir: Path, packet: dict[str, Any], diagnosis: dict[str, Any],
    source: str, config: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    maximum = max(1, int(config.get("maximum_shadow_challengers") or 4))
    expanded = {**config, "maximum_shadow_challengers": 1000}
    candidates = _candidate_sources(packet, diagnosis, source, expanded)
    from runtime.improvement_plugins.candidate_selection_shadow_prior import (
        prioritize_shadow_candidates,
    )

    ordered, trace = prioritize_shadow_candidates(
        root=root, project_dir=project_dir, candidates=candidates, packet=packet,
        failure_class=str(diagnosis.get("failure_class") or ""),
        minimum_support=int(config.get("minimum_shadow_prior_support") or 2),
    )
    return _diverse_candidates(ordered, maximum), trace


def _canonical_target(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    return re.sub(r"\s*\(\d+\s+loc\)\s*$", "", text, flags=re.IGNORECASE)


def _diverse_candidates(candidates: list[str], maximum: int) -> list[str]:
    families: dict[tuple[str, str], list[str]] = {}
    for candidate in candidates:
        families.setdefault(_candidate_family(candidate), []).append(candidate)
    heads = [values[0] for values in families.values()]
    tails = [candidate for values in families.values() for candidate in values[1:]]
    return [*heads, *tails][:maximum]


def _candidate_family(candidate: str) -> tuple[str, str]:
    path, _separator, qualified = candidate.partition(":")
    leaf = qualified.rsplit(".", 1)[-1]
    parts = [part for part in leaf.lower().split("_") if part]
    if len(parts) >= 3:
        return path.lower(), f"{parts[0]}:*:{parts[-1]}"
    if len(parts) == 2:
        return path.lower(), f"{parts[0]}:*"
    return path.lower(), leaf.lower()


def _candidate_rank(row: dict[str, Any]) -> tuple[int, int, int, str]:
    effects = list(row.get("side_effects") or [])
    return (
        int(bool(effects)),
        -int(str(row.get("kind") or "") in {"function", "method", "callable"}),
        -int(row.get("score") or 0),
        str(row.get("source") or ""),
    )


def _candidate_trial_blocked(row: dict[str, Any]) -> bool:
    reasons = " ".join(str(value).lower() for value in row.get("reasons") or [])
    effects = {str(value) for value in row.get("side_effects") or []}
    unsafe_rules = {
        "direct_memory_state_boundary",
        "external_effect_boundary",
        "stateful_method_effects",
    }
    return bool(effects) or any(rule in reasons for rule in unsafe_rules)


def _control(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": packet.get("status"),
        "project_min_score": float(packet.get("project_min_score") or 0.0),
        "role_scores": dict(packet.get("role_scores") or {}),
        "downstream_evidence": dict(packet.get("downstream_evidence") or {}),
        "selected_extraction_candidate": packet.get("selected_candidate"),
        "selected_candidate_quality": dict(packet.get("candidate_quality") or {}),
    }


def _trial(root: Path, project_dir: Path, control: dict[str, Any], challenger: str) -> dict[str, Any]:
    from runtime.self_improvement_training import _evaluate

    treatment = _evaluate(root, project_dir, write=True, evaluation_target=challenger)
    regressions = [
        role for role, score in dict(control.get("role_scores") or {}).items()
        if score is not None and dict(treatment.get("role_scores") or {}).get(role) is not None
        and float(treatment["role_scores"][role]) < float(score)
    ]
    delta = round(
        float(treatment.get("project_min_score") or 0.0)
        - float(control.get("project_min_score") or 0.0), 2,
    )
    downstream = dict(treatment.get("downstream_evidence") or {})
    selected = treatment.get("selected_extraction_candidate") == challenger
    executable = downstream.get("acceptance_signal") == "executable_callable"
    confirmed = delta > 0 and selected and executable and not regressions
    return {
        "status": "confirmed_selection_effect" if confirmed else "selection_effect_not_confirmed",
        "challenger": challenger,
        "score_delta": delta,
        "role_regressions": regressions,
        "selected": selected,
        "actual_selected": treatment.get("selected_extraction_candidate"),
        "acceptance_signal": downstream.get("acceptance_signal"),
        "treatment": treatment,
    }


def _trial_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "status", "challenger", "score_delta", "role_regressions",
            "selected", "actual_selected", "acceptance_signal",
        )
    } | ({
        "strategy": row["strategy"],
        "convergent_trial_count": row.get("convergent_trial_count"),
    } if row.get("strategy") else {})


def _convergent_effect(
    trials: list[dict[str, Any]], source: str, config: dict[str, Any]
) -> dict[str, Any] | None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in trials:
        actual = str(row.get("actual_selected") or "")
        if (
            actual and actual != source
            and float(row.get("score_delta") or 0.0) > 0
            and not row.get("role_regressions")
            and row.get("acceptance_signal") == "executable_callable"
        ):
            groups.setdefault(actual, []).append(row)
    minimum = max(2, int(config.get("minimum_emergent_confirmations") or 2))
    eligible = [(target, rows) for target, rows in groups.items() if len(rows) >= minimum]
    if not eligible:
        return None
    target, rows = sorted(
        eligible,
        key=lambda item: (-len(item[1]), -max(float(row["score_delta"]) for row in item[1]), item[0]),
    )[0]
    evidence = sorted(rows, key=lambda row: -float(row["score_delta"]))[0]
    return {
        **evidence,
        "status": "confirmed_selection_effect",
        "challenger": target,
        "selected": True,
        "actual_selected": target,
        "strategy": "stable_reselection_convergence",
        "convergent_trial_count": len(rows),
    }
