"""Validate advisory hypotheses without granting execution authority."""
from typing import Any
from .repair_assertion_contract import validate_assertion_plan


FORBIDDEN_FIELDS = {
    "allowed_operator_ids", "commands", "diff", "files", "operator_id", "patch",
    "replacement_source", "source_apply", "source_code",
}
ALLOWED_FIELDS = {
    "target", "failure_signature", "mechanism", "repair_mechanism",
    "mutation_contract", "residual_risks", "confidence",
}
MUTATION_FIELDS = {"precondition", "change", "preserved_behavior"}


def _validate_payload(
    payload: dict[str, Any], envelope: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    errors = []
    forbidden = _forbidden_keys(payload)
    if forbidden:
        errors.append("forbidden_fields:" + ",".join(sorted(forbidden)))
    allowed = ALLOWED_FIELDS | ({'reached_return_ids'} if envelope.get('reached_returns') else set())
    if envelope.get('edit_scope'):
        from .model_edit_scope import validate_related_targets
        allowed |= {'related_targets'}
        try:
            validate_related_targets(envelope['edit_scope'],payload.get('related_targets'))
        except ValueError as exc:
            errors.append(str(exc))
    if envelope.get('assertion_contract'):
        allowed |= {'assertion_plan'}
        try:
            validate_assertion_plan(envelope['assertion_contract'], payload.get('assertion_plan'))
        except ValueError as exc:
            errors.append(str(exc))
    unknown = set(str(key) for key in payload) - allowed
    if unknown:
        errors.append("unknown_fields:" + ",".join(sorted(unknown)))
    if payload.get("target") != envelope["target"]:
        errors.append("target_mismatch")
    if payload.get("failure_signature") != envelope["failure_signature"]:
        errors.append("failure_signature_mismatch")
    for name in ("mechanism", "repair_mechanism"):
        if len(str(payload.get(name) or "").strip()) < 24:
            errors.append(f"{name}_not_specific")
    raw_mutation = payload.get("mutation_contract")
    if not isinstance(raw_mutation, dict):
        errors.append("mutation_contract_object_required")
        mutation = {}
    else:
        mutation = dict(raw_mutation)
    unknown_mutation = set(str(key) for key in mutation) - MUTATION_FIELDS
    if unknown_mutation:
        errors.append("unknown_mutation_fields:" + ",".join(sorted(unknown_mutation)))
    for name in ("precondition", "change", "preserved_behavior"):
        if len(str(mutation.get(name) or "").strip()) < 12:
            errors.append(f"mutation_contract_{name}_required")
    if envelope.get('reached_returns'):
        required = [r['id'] for r in envelope['reached_returns']]
        if payload.get('reached_return_ids') != required:
            errors.append('reached_return_binding_mismatch')
    raw_confidence = payload.get("confidence")
    try:
        confidence = float(raw_confidence) if not isinstance(raw_confidence, bool) else -1.0
    except (TypeError, ValueError):
        confidence = -1.0
    if not 0.0 <= confidence <= 1.0:
        errors.append("confidence_out_of_range")
    elif confidence < 0.6:
        errors.append("confidence_below_threshold")
    raw_risks = payload.get("residual_risks")
    risks = _strings(raw_risks) if isinstance(raw_risks, list) else []
    if not risks or not all(isinstance(value, str) and value.strip() for value in raw_risks or []):
        errors.append("residual_risks_required")
    normalized = {
        "mechanism": str(payload.get("mechanism") or "")[:1200],
        "repair_mechanism": str(payload.get("repair_mechanism") or "")[:1200],
        "mutation_contract": {key: str(mutation.get(key) or "")[:800] for key in (
            "precondition", "change", "preserved_behavior"
        )},
        "residual_risks": risks[:8],
        "confidence": round(confidence, 3),
    }
    return normalized, sorted(set(errors))


def _forbidden_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            *{str(key) for key in value if str(key) in FORBIDDEN_FIELDS},
            *(key for child in value.values() for key in _forbidden_keys(child)),
        }
    if isinstance(value, list):
        return {key for child in value for key in _forbidden_keys(child)}
    return set()


def _strings(values: Any) -> list[str]:
    if isinstance(values, (str, bytes)):
        return [str(values)] if values else []
    return [str(value) for value in values or [] if value]


