"""Bounded LLM advisory for failure mechanisms absent from the local KB."""

from __future__ import annotations

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .bounded_prompt_json import bounded_prompt_json
from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


FORBIDDEN_FIELDS = {
    "allowed_operator_ids", "commands", "diff", "files", "operator_id", "patch",
    "replacement_source", "source_apply", "source_code",
}
ALLOWED_FIELDS = {
    "target", "failure_signature", "mechanism", "repair_mechanism",
    "mutation_contract", "residual_risks", "confidence",
}
MUTATION_FIELDS = {"precondition", "change", "preserved_behavior"}


def enrich_with_llm_failure_hypothesis(
    diagnosis: dict[str, Any], *, project_dir: Path,
    config: LocalInferenceConfig | None,
) -> dict[str, Any]:
    result = deepcopy(diagnosis)
    if config is None:
        return result
    for issue in result.get("issues") or []:
        if not isinstance(issue, dict) or not _eligible(issue):
            continue
        advisory = build_llm_failure_hypothesis(
            issue=issue, project_dir=project_dir, config=config
        )
        issue["llm_hypothesis_advisory"] = advisory
        if advisory.get("status") != "accepted_hypothesis_only":
            continue
        issue["causal_hypothesis"] = dict(advisory["causal_hypothesis"])
        issue["repair_design"] = dict(advisory["repair_design"])
        issue["proposed_operator_ids"] = []
        issue["allowed_operator_ids"] = []
    return result


def build_llm_failure_hypothesis(
    *, issue: dict[str, Any], project_dir: Path, config: LocalInferenceConfig,
) -> dict[str, Any]:
    targets = _strings(issue.get("affected_targets"))
    failures = [dict(row) for row in issue.get("failure_evidence") or [] if isinstance(row, dict)]
    target = targets[0] if len(targets) == 1 else ""
    failure = failures[0] if len(failures) == 1 else {}
    source = _target_source(project_dir, target) if target else ""
    envelope = _evidence_envelope(target=target, failure=failure, source=source)
    if (
        not target or not failure or not source or not envelope["failure_signature"]
        or str(failure.get("target") or target) != target
    ):
        return _advisory("rejected", envelope, ["single_source_backed_failure_required"])
    try:
        payload = call_json_chat(_messages(envelope), config=config)
    except LocalInferenceError as exc:
        return _advisory("unavailable", envelope, [str(exc)[:240]])
    if not isinstance(payload, dict):
        return _advisory("rejected", envelope, ["response_object_required"], payload=payload)
    normalized, errors = _validate_payload(payload, envelope)
    if errors:
        return _advisory("rejected", envelope, errors, payload=payload)
    evidence = [
        f"failure_signature:{envelope['failure_signature']}",
        f"target_source:{target}",
        f"source_digest:{envelope['source_digest']}",
        f"llm_response:{_digest(payload)}",
    ]
    mechanism = str(normalized["mechanism"])
    repair_mechanism = str(normalized["repair_mechanism"])
    mutation = dict(normalized["mutation_contract"])
    advisory = _advisory("accepted_hypothesis_only", envelope, [], payload=payload)
    advisory.update({
        "confidence": normalized["confidence"],
        "causal_hypothesis": {
            "status": "llm_hypothesis_review_required",
            "mechanism": mechanism,
            "evidence": evidence,
            "execution_authority": False,
        },
        "repair_design": {
            "status": "llm_hypothesis_review_required",
            "target": target,
            "mechanism": repair_mechanism,
            "mutation_contract": mutation,
            "evidence": evidence,
            "residual_risks": normalized["residual_risks"],
            "execution_authority": False,
            "source_apply": False,
            "promotion_allowed": False,
        },
    })
    return advisory


def _eligible(issue: dict[str, Any]) -> bool:
    return bool(
        issue.get("failure_specific_reducer_required") is True
        and issue.get("failure_evidence")
        and not issue.get("causal_hypothesis")
    )


def _evidence_envelope(*, target: str, failure: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "target": target,
        "failure_signature": str(failure.get("failure_signature") or ""),
        "failure_detail": str(failure.get("detail") or "")[:1200],
        "failing_nodeids": _strings(failure.get("failing_nodeids"))[:8],
        "source_digest": hashlib.sha256(source.encode("utf-8")).hexdigest() if source else "",
        "source_excerpt": source[:8000],
    }


def _target_source(project_dir: Path, target: str) -> str:
    path_text, _, symbol = target.partition(":")
    try:
        root = project_dir.resolve(strict=True)
        path = (root / path_text).resolve(strict=True)
    except OSError:
        return ""
    if not path.is_relative_to(root):
        return ""
    if not path.is_file() or path.suffix.lower() != ".py":
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, UnicodeError, SyntaxError):
        return ""
    leaf = symbol.rsplit(".", 1)[-1]
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == leaf
    ]
    return ast.get_source_segment(text, candidates[0]) or "" if len(candidates) == 1 else ""


def _messages(envelope: dict[str, Any]) -> list[dict[str, str]]:
    schema = {
        "target": envelope["target"],
        "failure_signature": envelope["failure_signature"],
        "mechanism": "specific causal explanation grounded in the supplied source and failure",
        "repair_mechanism": "abstract behavior change, without code or patch text",
        "mutation_contract": {
            "precondition": "source condition that makes the change applicable",
            "change": "abstract semantic change",
            "preserved_behavior": "behavior that must remain unchanged",
        },
        "residual_risks": ["specific risk"],
        "confidence": 0.0,
    }
    return [
        {
            "role": "system",
            "content": (
                "Return one JSON object only. Diagnose the supplied Python failure without writing code. "
                "Use exactly the supplied target and failure_signature. Do not return patches, diffs, "
                "commands, files, source code, replacement functions, or operator identifiers. "
                "The result is a hypothesis with no execution authority. Required schema: "
                + json.dumps(schema, ensure_ascii=False)
            ),
        },
        {"role": "user", "content": bounded_prompt_json(envelope, max_chars=12000)},
    ]


def _validate_payload(
    payload: dict[str, Any], envelope: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    errors = []
    forbidden = _forbidden_keys(payload)
    if forbidden:
        errors.append("forbidden_fields:" + ",".join(sorted(forbidden)))
    unknown = set(str(key) for key in payload) - ALLOWED_FIELDS
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


def _advisory(
    status: str, envelope: dict[str, Any], errors: list[str],
    *, payload: Any = None,
) -> dict[str, Any]:
    return {
        "artifact_type": "ProjectDevelopmentLlmHypothesisAdvisory",
        "schema_version": "project_development_llm_hypothesis_advisory.v1",
        "status": status,
        "authority": "hypothesis_only",
        "target": envelope.get("target"),
        "failure_signature": envelope.get("failure_signature"),
        "source_digest": envelope.get("source_digest"),
        "model_response_digest": _digest(payload) if payload is not None else None,
        "errors": errors,
        "execution_authorized": False,
        "source_changes": False,
        "automatic_promotion": False,
    }


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


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
