"""Project-stratum classification for role/project-type evaluation."""

from __future__ import annotations

import json
import re
from typing import Any

from .project_type_token_matcher import marker_matches, match_project_stratum
from .role_project_type_evaluation_policy import load_role_project_type_policy


# Compatibility exports for the evaluation facade; new code should use the matcher module.
_marker_matches = marker_matches
_matched_stratum = match_project_stratum


def classify_project_case(
    case: dict[str, Any], *, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Classify one case without granting the classification any scoring authority."""
    config = policy or load_role_project_type_policy()
    explicit = dict(case.get("project_classification") or {})
    explicit_id = str(case.get("project_stratum") or "")
    classification_version = str(config.get("classification_version") or "")
    compatible_versions = {
        classification_version,
        *(str(value) for value in config.get("compatible_classification_versions") or []),
    }
    if (
        explicit.get("schema_version") == "role_project_classification.v1"
        and explicit.get("policy_version") in compatible_versions
    ):
        explicit_id = str(explicit.get("project_stratum") or explicit_id)
    strata = {str(row["id"]): dict(row) for row in config["strata"]}
    project_name = str(case.get("project") or case.get("name") or "").lower()
    identity_override = next((
        dict(row) for row in config.get("project_identity_overrides", [])
        if str(row.get("project_contains") or "").lower() in project_name
        and str(row.get("project_stratum") or "") in strata
    ), None)
    evidence = _classification_evidence(case)
    archetype = _project_archetype(evidence, case)
    contract_family = _contract_family(evidence, case)
    project_shape = _project_shape(evidence, case)
    identity_text = _normalized_text({
        "project": case.get("project"),
        "archetype": archetype,
        "contract_family": contract_family,
        "project_shape": project_shape,
    })
    authoritative_text = _normalized_text({
        "archetype": archetype,
        "contract_family": contract_family,
    })

    if identity_override:
        selected = strata[str(identity_override["project_stratum"])]
        source = "identity_override"
        matched = [str(identity_override["project_contains"])]
    elif explicit_id in strata and explicit_id != "unknown_new_archetype":
        selected = strata[explicit_id]
        source = "explicit"
        matched = [explicit_id]
    elif contract_override := _contract_family_override(contract_family, config, strata):
        selected = strata[contract_override["project_stratum"]]
        source = "contract_family_precedence"
        matched = [contract_override["marker"]]
    else:
        matcher_text = authoritative_text if (archetype or contract_family) else identity_text
        selected, matched = match_project_stratum(
            config["strata"], matcher_text, identity_text, authoritative_text
        )
        source = (
            "evidence_match" if matched
            else "fallback_authoritative_unmatched" if (archetype or contract_family)
            else "fallback"
        )

    pre_entrypoint_stratum = str(selected["id"])
    entrypoint_override = _plugin_identity_override(evidence, config) or _entrypoint_identity_override(
        case=case,
        evidence=evidence,
        selected_id=str(selected["id"]),
        policy=config,
    )
    if entrypoint_override:
        selected = strata[str(entrypoint_override["project_stratum"])]
        source = "entrypoint_identity_precedence"
        matched = [str(entrypoint_override["evidence_marker"]), "project_map_entrypoint"]

    risk_text = _normalized_text({
        **_risk_evidence(case, evidence, archetype, contract_family, project_shape),
        "project_report_signals": _project_report_risk_signals(evidence, config),
    })
    risk_profiles = []
    for row in config.get("risk_profiles", []):
        markers = [str(item).lower() for item in row.get("markers", [])]
        if any(marker_matches(marker, risk_text) for marker in markers):
            risk_profiles.append(str(row["id"]))
    if not risk_profiles:
        risk_profiles = [
            str(value) for value in
            dict(config.get("default_risk_profiles_by_stratum") or {}).get(str(selected["id"]), [])
        ] or ["unspecified"]
    project_name_text = _normalized_text({"project": case.get("project")})
    name_stratum, name_markers = match_project_stratum(
        config["strata"], project_name_text, project_name_text, ""
    )
    name_stratum_id = str(name_stratum["id"]) if name_markers else None
    return {
        "schema_version": "role_project_classification.v1",
        "policy_version": classification_version,
        "project_stratum": str(selected["id"]),
        "stratum_label": str(selected.get("label") or selected["id"]),
        "project_archetype": archetype or None,
        "project_archetype_scope": (
            "internal_capability"
            if entrypoint_override and archetype and pre_entrypoint_stratum != str(selected["id"])
            else "project_identity"
        ),
        "effective_project_identity": str(selected["id"]),
        "contract_family": contract_family or None,
        "project_shape": project_shape or None,
        "project_subtype": (
            explicit.get("project_subtype")
            or case.get("project_subtype")
            or ("argv_json_stdout_json" if case.get("cli_evidence") else None)
            or (f"operator:{case.get('operator_id')}" if case.get("operator_id") else None)
        ),
        "risk_profiles": sorted(set(risk_profiles)),
        "classification_source": source,
        "matched_markers": matched,
        "project_name_stratum": name_stratum_id,
        "classification_conflict": bool(
            archetype and name_stratum_id and name_stratum_id != str(selected["id"])
        ),
    }


def _classification_evidence(case: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "project": case.get("project"),
        "project_stratum": case.get("project_stratum"),
        "archetype": case.get("archetype"),
        "contract_family": case.get("contract_family"),
        "scope_classification": case.get("scope_classification"),
        "project_classification": case.get("project_classification"),
        "selected_candidate_quality": case.get("selected_candidate_quality"),
        "architect_first_slice": case.get("architect_first_slice"),
    }
    artifacts = dict(case.get("artifacts") or {})
    for key in ("project_map_report", "architecture_decision", "technical_spec"):
        if key in artifacts:
            evidence[key] = artifacts[key]
    return evidence


def _plugin_identity_override(
    evidence: dict[str, Any], policy: dict[str, Any]
) -> dict[str, str] | None:
    rule = dict(policy.get("plugin_identity_precedence") or {})
    project_map = dict(evidence.get("project_map_report") or {})
    content = dict(project_map.get("content") or project_map)
    source_health = dict(content.get("source_health") or {})
    count = int(source_health.get("declared_plugin_entrypoint_count") or 0)
    if count < int(rule.get("minimum_entrypoint_count") or 1):
        return None
    target = str(rule.get("project_stratum") or "")
    if not target:
        return None
    return {"project_stratum": target, "evidence_marker": "declared_plugin_entrypoint"}


def _entrypoint_identity_override(
    *, case: dict[str, Any], evidence: dict[str, Any], selected_id: str, policy: dict[str, Any]
) -> dict[str, str] | None:
    rule = dict(policy.get("entrypoint_identity_precedence") or {})
    target = str(rule.get("project_stratum") or "")
    direct_selected = selected_id in {str(value) for value in rule.get("when_selected") or []}
    low_confidence_selected = (
        selected_id in {str(value) for value in rule.get("when_selected_low_confidence") or []}
        and _project_archetype_confidence(evidence)
        <= float(rule.get("maximum_archetype_confidence") or 0.0)
    )
    if not target or not (direct_selected or low_confidence_selected):
        return None
    project_map = dict(evidence.get("project_map_report") or {})
    content = dict(project_map.get("content") or project_map)
    source_health = dict(content.get("source_health") or {})
    if int(source_health.get("entrypoint_count") or 0) < int(rule.get("minimum_entrypoint_count") or 1):
        return None
    project_name = str(case.get("project") or case.get("name") or "").lower()
    patterns = [str(pattern) for pattern in rule.get("project_name_patterns") or []]
    declared_script = (
        rule.get("declared_script_entrypoint_precedence") is True
        and int(source_health.get("declared_script_entrypoint_count") or 0) > 0
    )
    if low_confidence_selected and not declared_script:
        return None
    project_name_match = any(re.search(pattern, project_name, re.IGNORECASE) for pattern in patterns)
    if not declared_script and not project_name_match:
        return None
    return {
        "project_stratum": target,
        "evidence_marker": "declared_script_entrypoint" if declared_script else "project_name",
    }


def _project_archetype_confidence(evidence: dict[str, Any]) -> float:
    project_map = dict(evidence.get("project_map_report") or {})
    content = dict(project_map.get("content") or project_map)
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or answers.get("scope") or {})
    profile = dict(scope.get("domain_profile") or content.get("domain_profile") or {})
    return float(profile.get("confidence") or 0.0)


def _project_archetype(evidence: dict[str, Any], case: dict[str, Any]) -> str:
    project_map = dict(evidence.get("project_map_report") or {})
    content = dict(project_map.get("content") or project_map)
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or answers.get("scope") or {})
    profile = dict(scope.get("domain_profile") or content.get("domain_profile") or {})
    if profile.get("kind"):
        return str(profile["kind"])
    architecture = dict(evidence.get("architecture_decision") or {})
    architecture_content = dict(architecture.get("content") or architecture)
    carried = dict(dict(architecture_content.get("project_profile") or {}).get("domain_profile") or {})
    if carried.get("kind"):
        return str(carried["kind"])
    explicit = dict(case.get("project_classification") or {})
    return str(
        case.get("archetype") or explicit.get("project_archetype")
        or _first_value(evidence, ("archetype", "project_archetype", "domain_profile_kind"))
        or ""
    )


def _contract_family(evidence: dict[str, Any], case: dict[str, Any]) -> str:
    technical_spec = dict(evidence.get("technical_spec") or {})
    content = dict(technical_spec.get("content") or technical_spec)
    extraction = dict(content.get("extraction_contract") or {})
    explicit = dict(case.get("project_classification") or {})
    return str(
        extraction.get("contract_family") or case.get("contract_family")
        or explicit.get("contract_family") or _first_value(evidence, ("contract_family",)) or ""
    )


def _project_shape(evidence: dict[str, Any], case: dict[str, Any]) -> str:
    project_map = dict(evidence.get("project_map_report") or {})
    content = dict(project_map.get("content") or project_map)
    source_health = dict(content.get("source_health") or {})
    explicit = dict(case.get("project_classification") or {})
    return str(
        source_health.get("project_shape") or explicit.get("project_shape")
        or _first_value(case.get("scope_classification"), ("project_shape",)) or ""
    )


def _risk_evidence(
    case: dict[str, Any], evidence: dict[str, Any],
    archetype: str, contract_family: str, project_shape: str,
) -> dict[str, Any]:
    quality = dict(case.get("selected_candidate_quality") or {})
    return {
        "declared": dict(case.get("project_classification") or {}).get("risk_profiles"),
        # A bounded extraction contract is more specific than the repository-wide
        # archetype. Effects remain authoritative below.
        "archetype": archetype if not contract_family else None,
        "contract_family": contract_family,
        "project_shape": project_shape,
        "selection_kind": dict(quality.get("selection_evidence") or {}).get("kind"),
        "observed_side_effects": dict(quality.get("structural_evidence") or {}).get("observed_side_effects"),
        "side_effect_policy": _active_side_effect_policy(
            _first_object(evidence, "side_effect_policy")
        ),
    }


def _project_report_risk_signals(
    evidence: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    project_map = dict(evidence.get("project_map_report") or {})
    content = dict(project_map.get("content") or project_map)
    answers = dict(content.get("answers") or {})
    execution_value = answers.get("2_execution") or answers.get("execution") or {}
    capabilities_value = answers.get("3_capabilities") or answers.get("capabilities") or {}
    execution = dict(execution_value) if isinstance(execution_value, dict) else {}
    capabilities = dict(capabilities_value) if isinstance(capabilities_value, dict) else {}
    effects = {
        str(effect)
        for row in execution.get("central_flow_nodes") or []
        if isinstance(row, dict)
        for effect in row.get("side_effects") or []
    }
    inference = dict(policy.get("project_report_risk_inference") or {})
    signals = {
        str(risk)
        for effect, risk in dict(inference.get("direct_effect_risks") or {}).items()
        if str(effect) in effects
    }
    for combination in inference.get("stateful_effect_combinations") or []:
        if {str(value) for value in combination} <= effects:
            signals.add("stateful")
    if any(isinstance(row, dict) for row in capabilities.get("pure_transforms") or []):
        pure_risk = str(inference.get("pure_candidate_risk") or "")
        if pure_risk:
            signals.add(pure_risk)
    return sorted(signals)


def _active_side_effect_policy(value: Any) -> Any:
    """Keep asserted effects while discarding disabled policy switches."""
    if isinstance(value, dict):
        active = {}
        for key, item in value.items():
            if item is True:
                active[key] = True
            elif item is False or item is None:
                continue
            else:
                nested = _active_side_effect_policy(item)
                if nested not in ({}, [], ""):
                    active[key] = nested
        return active
    if isinstance(value, list):
        return [item for item in (_active_side_effect_policy(row) for row in value) if item not in ({}, [], "")]
    return value


def _contract_family_override(
    contract_family: str,
    policy: dict[str, Any],
    strata: dict[str, dict[str, Any]],
) -> dict[str, str] | None:
    text = _normalized_text({"contract_family": contract_family})
    for raw in policy.get("contract_family_precedence") or []:
        row = dict(raw)
        target = str(row.get("project_stratum") or "")
        marker = str(row.get("marker") or "")
        if target in strata and marker_matches(marker, text):
            return {"project_stratum": target, "marker": marker}
    return None


def _first_object(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _first_object(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _first_object(value, key)
            if found is not None:
                return found
    return None


def _first_value(payload: Any, keys: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            found = _first_value(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _first_value(value, keys)
            if found:
                return found
    return ""


def _normalized_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).lower().replace("-", "_")
    except (TypeError, ValueError):
        return str(value).lower().replace("-", "_")

