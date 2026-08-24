"""Portable semantic signatures shared by self-improvement stages."""

from __future__ import annotations

from typing import Any


def portable_failure_signature(
    report: dict[str, Any], normalization: dict[str, Any] | None = None
) -> str:
    policy = normalization or {}
    baseline = dict(report.get("baseline") or {})
    diagnosis = dict(report.get("diagnosis") or {})
    evidence = dict(baseline.get("downstream_evidence") or {})
    quality = dict(baseline.get("selected_candidate_quality") or {})
    structural = dict(quality.get("structural_evidence") or {})
    effects = ",".join(
        sorted(str(value) for value in structural.get("observed_side_effects") or [])
    )
    signature = "|".join([
        str(evidence.get("reason") or evidence.get("acceptance_signal")
            or diagnosis.get("failure_class") or "unclassified"),
        effects or "pure",
        str(structural.get("output_inference_basis") or "unknown"),
    ])
    return normalize_portable_signature(signature, policy)


def diagnosis_envelope(
    report: dict[str, Any], normalization: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Describe the portable invariants without collapsing them into one opaque key."""
    policy = normalization or {}
    signature = portable_failure_signature(report, policy)
    failure_class, effects, output_family = signature_parts(signature)
    output_members = list(
        dict(policy.get("output_basis_families") or {}).get(output_family) or []
    )
    return {
        "artifact_type": "FailureDiagnosisEnvelope",
        "portable_signature": signature,
        "failure_class": failure_class,
        "required_effects": sorted(effects),
        "effect_match_mode": str(policy.get("effect_match_mode") or "exact"),
        "output_family": output_family,
        "accepted_output_bases": sorted({output_family, *map(str, output_members)}),
        "semantic_context": semantic_context(report),
    }


def semantic_context(report: dict[str, Any]) -> list[str]:
    """Keep measured contract identity separate from the structural signature."""
    baseline = dict(report.get("baseline") or {})
    quality = dict(baseline.get("selected_candidate_quality") or {})
    values = [
        *list(quality.get("contract_archetype_ids") or []),
        *list(quality.get("semantic_profile_ids") or []),
    ]
    failure_family = executable_failure_family(report)
    if failure_family:
        return [f"executable_failure:{failure_family}"]
    return sorted({str(value) for value in values if value})


def executable_failure_family(report: dict[str, Any]) -> str:
    baseline = dict(report.get("baseline") or {})
    downstream = dict(baseline.get("downstream_evidence") or {})
    summary = dict(downstream.get("summary") or {})
    skipped = [dict(row) for row in summary.get("skipped_targets") or [] if isinstance(row, dict)]
    reasons = {str(row.get("reason") or "") for row in skipped}
    details = " ".join(str(row.get("detail") or "").lower() for row in skipped)
    if "import_failed_runtime_error" in reasons:
        return "import_runtime_error"
    if "requested unknown topic" in details:
        return "domain_fixture_missing"
    if "working outside of application context" in details:
        return "framework_context_missing"
    if "_safemethodattribute" in details or (
        "object has no attribute '_" in details
    ):
        return "receiver_materialization_mismatch"
    if "_stubobject" in details and "unsupported operand" in details:
        return "dependency_stub_operation_mismatch"
    if "filenotfounderror" in details and (
        "library not found" in details or "compile the library" in details
    ):
        return "external_runtime_artifact_missing"
    if ("dimension" in details or "shape" in details) and (
        "mismatch" in details or "!=" in details
    ):
        return "sample_shape_mismatch"
    if (
        "number of splits" in details or "n_splits=" in details
    ) and (
        "number of samples" in details or "n_samples=" in details
    ):
        return "sample_shape_mismatch"
    if any(pattern in details for pattern in (
        "object has no attribute 'value'",
        "object has no attribute 'items'",
        "'nonetype' object has no attribute",
        "object of type 'nonetype' has no len()",
        "bytes-like object is required, not 'nonetype'",
    )):
        return "argument_materialization_mismatch"
    if "filenotfounderror" in details and ("none/" in details or "none\\" in details):
        return "argument_materialization_mismatch"
    return ""


def normalize_portable_signature(signature: str, normalization: dict[str, Any]) -> str:
    parts = str(signature).split("|", 2)
    if len(parts) != 3:
        return signature
    failure_class = normalize_failure_class(parts[0], normalization)
    output = parts[2]
    for family, values in dict(normalization.get("output_basis_families") or {}).items():
        if output in {str(value) for value in values or []}:
            output = str(family)
            break
    return "|".join([failure_class, parts[1], output])


def normalize_failure_class(value: str, normalization: dict[str, Any]) -> str:
    candidate = str(value or "unknown")
    for family, members in dict(normalization.get("failure_class_families") or {}).items():
        if candidate == str(family) or candidate in {str(item) for item in members or []}:
            return str(family)
    return candidate


def signature_parts(signature: str) -> tuple[str, set[str], str]:
    parts = str(signature).split("|", 2)
    if len(parts) != 3:
        return str(signature), set(), "unknown"
    effects = {
        value for value in parts[1].split(",") if value and value != "pure"
    }
    return parts[0], effects, parts[2]


def assess_signature_match(
    actual: str, expected: str, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return an auditable match decision and preserve useful negative evidence."""
    settings = policy or {}
    actual_class, actual_effects, actual_output = signature_parts(actual)
    expected_class, expected_effects, expected_output = signature_parts(expected)
    class_match = actual_class == expected_class
    missing_effects = expected_effects - actual_effects
    additional_effects = actual_effects - expected_effects
    forbidden_effects = additional_effects & {
        str(value) for value in settings.get("forbidden_additional_effects") or []
    }
    subset_mode = settings.get("effect_match_mode") == "required_subset"
    effects_match = (
        not missing_effects and not forbidden_effects
        and (subset_mode or not additional_effects)
    )
    output_match = actual_output == expected_output
    matched = class_match and effects_match and output_match
    score = round(
        (0.4 if class_match else 0.0)
        + (0.35 if effects_match else 0.0)
        + (0.25 if output_match else 0.0),
        2,
    )
    if matched and not additional_effects:
        kind = "exact"
    elif matched:
        kind = "compatible"
    elif class_match and score >= float(settings.get("near_match_score") or 0.65):
        kind = "near_contrast"
    else:
        kind = "unrelated"
    return {
        "matched": matched,
        "match_kind": kind,
        "score": score,
        "class_match": class_match,
        "effects_match": effects_match,
        "output_match": output_match,
        "missing_effects": sorted(missing_effects),
        "additional_effects": sorted(additional_effects),
        "forbidden_additional_effects": sorted(forbidden_effects),
        "actual_output_family": actual_output,
        "expected_output_family": expected_output,
    }


def signatures_match(actual: str, expected: str, policy: dict[str, Any]) -> bool:
    return bool(assess_signature_match(actual, expected, policy)["matched"])


def recovery_metrics(probes: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure retrieval and diagnosis quality without inventing a readiness score."""
    measured = [row for row in probes if row.get("status") != "probe_failed"]
    matched = [row for row in measured if row.get("matches_hypothesis")]
    same_class = [
        row for row in measured
        if dict(row.get("signature_assessment") or {}).get("class_match")
    ]
    contrasts = [
        row for row in measured
        if dict(row.get("signature_assessment") or {}).get("match_kind") == "near_contrast"
    ]
    aligned_probes = [row for row in measured if row.get("retrieval_alignment")]
    aligned = [
        row for row in aligned_probes
        if dict(row.get("retrieval_alignment") or {}).get("aligned")
    ]
    count = len(measured)
    return {
        "probed_project_count": count,
        "matching_project_count": len(matched),
        "near_contrast_project_count": len(contrasts),
        "same_failure_class_project_count": len(same_class),
        "matching_yield": round(len(matched) / count, 4) if count else 0.0,
        "signature_discrimination": (
            round(len(matched) / len(same_class), 4) if same_class else 0.0
        ),
        "target_alignment_count": len(aligned),
        "target_alignment_measured_count": len(aligned_probes),
        "target_alignment_rate": (
            round(len(aligned) / len(aligned_probes), 4) if aligned_probes else None
        ),
        "target_drift_projects": sorted(
            str(row.get("project") or "") for row in aligned_probes if row not in aligned
        ),
        "contrast_signatures": sorted({
            str(row.get("portable_signature") or "") for row in contrasts
            if row.get("portable_signature")
        }),
    }
