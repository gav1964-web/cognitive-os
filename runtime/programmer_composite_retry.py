"""One bounded schema-correction retry for composite L4.5 candidates."""

from __future__ import annotations

import json
from typing import Any, Callable

from .local_inference import LocalInferenceConfig, LocalInferenceError
from .bounded_prompt_json import bounded_prompt_json
from .programmer_llm_candidate_contract import candidate_errors, normalize_recipe
from .programmer_repair_playbooks import repair_recipe_errors


def retry_composite_payload(
    *,
    evidence: dict[str, Any],
    normalized: dict[str, Any],
    initial_payload: dict[str, Any],
    messages: list[dict[str, str]],
    config: LocalInferenceConfig,
    caller: Callable[..., dict[str, Any]],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    diagnostic = diagnostics if diagnostics is not None else {}
    diagnostic.update({"attempted": False, "rejection_errors": [], "status": "not_required"})
    changes = [dict(item) for item in list(evidence.get("change_targets") or [])]
    recipe = dict(normalized.get("patch_recipe_hypothesis") or {})
    errors = candidate_errors(
        recipe,
        str(evidence.get("target") or ""),
        str(evidence.get("source_excerpt") or ""),
        allowed_targets=[str(item.get("target") or "") for item in changes],
        source_excerpts={str(item.get("target") or ""): str(item.get("source_excerpt") or "") for item in changes},
    )
    errors.extend(repair_recipe_errors(recipe, list(evidence.get("repair_playbooks") or [])))
    if normalized.get("action") != "propose_patch_recipe":
        errors.append("composite_recipe_not_proposed")
    if len(changes) > 1 and not list(recipe.get("edits") or []):
        errors.append("missing_composite_edits")
    if not errors:
        return None
    unique_errors = list(dict.fromkeys(errors))
    diagnostic.update({"attempted": True, "rejection_errors": unique_errors, "status": "requested"})
    if len(changes) <= 1:
        return _retry_single_target(
            evidence=evidence,
            initial_payload=initial_payload,
            messages=messages,
            config=config,
            caller=caller,
            diagnostic=diagnostic,
            errors=unique_errors,
        )
    correction = (
        "Correct the previous JSON candidate. Rejection errors: "
        + ", ".join(unique_errors)
        + ". Return propose_patch_recipe with replace_functions and one complete edits item per required target. "
        "Each replacement_source must contain exactly one function declaration with its existing signature. "
        "Never include imports, markdown, module constants, or a second function in replacement_source."
    )
    retry_messages = [
        *messages,
        {"role": "assistant", "content": json.dumps(initial_payload, ensure_ascii=False, sort_keys=True)},
        {"role": "user", "content": correction},
    ]
    try:
        retry = caller(retry_messages, config=config)
        diagnostic.update(
            {
                "status": "received",
                "result_action": str(retry.get("action") or ""),
            }
        )
        if _payload_errors(retry, evidence, changes):
            decomposed = _retry_per_target(
                evidence=evidence,
                changes=changes,
                messages=messages,
                config=config,
                caller=caller,
                diagnostic=diagnostic,
            )
            if decomposed is not None:
                return decomposed
        return retry
    except LocalInferenceError as exc:
        diagnostic.update({"status": "unavailable", "error": str(exc)[:240]})
        return None


def _retry_single_target(
    *,
    evidence: dict[str, Any],
    initial_payload: dict[str, Any],
    messages: list[dict[str, str]],
    config: LocalInferenceConfig,
    caller: Callable[..., dict[str, Any]],
    diagnostic: dict[str, Any],
    errors: list[str],
) -> dict[str, Any] | None:
    correction = (
        "Correct the previous JSON candidate. Rejection errors: "
        + ", ".join(errors)
        + ". Return one replace_function recipe for the exact target. The replacement must make an AST-level code "
        "change that explains the exact expected-versus-got counterexample. Apply relevant repair_playbooks from "
        "the supplied evidence and preserve already passing cases. Selected repair playbooks: "
        + bounded_prompt_json(evidence.get("repair_playbooks") or [], max_chars=2500)
        + ". Return JSON only."
    )
    retry_messages = [
        *messages,
        {"role": "assistant", "content": json.dumps(initial_payload, ensure_ascii=False, sort_keys=True)},
        {"role": "user", "content": correction},
    ]
    try:
        retry = caller(retry_messages, config=config)
    except LocalInferenceError as exc:
        diagnostic.update({"status": "unavailable", "error": str(exc)[:240]})
        return None
    diagnostic.update({"status": "received", "result_action": str(retry.get("action") or "")})
    retry_errors = _single_payload_errors(retry, evidence)
    if not retry_errors:
        return retry
    diagnostic["secondary_rejection_errors"] = retry_errors
    final_messages = [
        *retry_messages,
        {"role": "assistant", "content": json.dumps(retry, ensure_ascii=False, sort_keys=True)},
        {
            "role": "user",
            "content": (
                "The corrected candidate still violates: "
                + ", ".join(retry_errors)
                + ". Correct those exact contract violations. Use the exact target function name and implement the "
                "selected verifier-derived playbook literally. Return JSON only."
            ),
        },
    ]
    try:
        final = caller(final_messages, config=config)
    except LocalInferenceError as exc:
        diagnostic.update({"status": "secondary_unavailable", "error": str(exc)[:240]})
        return retry
    diagnostic.update({"status": "secondary_received", "result_action": str(final.get("action") or "")})
    return final


def _single_payload_errors(payload: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    recipe = normalize_recipe(payload)
    target = str(evidence.get("target") or "")
    errors = candidate_errors(
        recipe,
        target,
        str(evidence.get("source_excerpt") or ""),
        allowed_targets=[target],
        source_excerpts={target: str(evidence.get("source_excerpt") or "")},
    )
    errors.extend(repair_recipe_errors(recipe, list(evidence.get("repair_playbooks") or [])))
    if payload.get("action") != "propose_patch_recipe":
        errors.append("target_recipe_not_proposed")
    return list(dict.fromkeys(errors))


def _payload_errors(payload: dict[str, Any], evidence: dict[str, Any], changes: list[dict[str, Any]]) -> list[str]:
    recipe = normalize_recipe(payload)
    errors = candidate_errors(
        recipe,
        str(evidence.get("target") or ""),
        str(evidence.get("source_excerpt") or ""),
        allowed_targets=[str(item.get("target") or "") for item in changes],
        source_excerpts={str(item.get("target") or ""): str(item.get("source_excerpt") or "") for item in changes},
    )
    if payload.get("action") != "propose_patch_recipe":
        errors.append("composite_recipe_not_proposed")
    return list(dict.fromkeys(errors))


def _retry_per_target(
    *,
    evidence: dict[str, Any],
    changes: list[dict[str, Any]],
    messages: list[dict[str, str]],
    config: LocalInferenceConfig,
    caller: Callable[..., dict[str, Any]],
    diagnostic: dict[str, Any],
) -> dict[str, Any] | None:
    edits = []
    target_results = []
    obligations = list(evidence.get("acceptance_obligations") or [])
    for change in changes:
        target = str(change.get("target") or "")
        target_evidence = {
            "target": target,
            "source_excerpt": change.get("source_excerpt"),
            "source_context": change.get("source_context"),
            "acceptance_obligations": [item for item in obligations if dict(item).get("target") == target],
            "implementation_delta": evidence.get("implementation_delta"),
        }
        correction = (
            "The composite response was invalid. Return one JSON object with action propose_patch_recipe and "
            "patch_recipe_hypothesis using edit_format replace_function, this exact target_symbol, and one complete "
            "replacement_source with the existing signature. Do not return edits, diff, imports, or markdown. "
            "Target evidence: " + bounded_prompt_json(target_evidence, max_chars=6000)
        )
        try:
            payload = caller([messages[0], {"role": "user", "content": correction}], config=config)
        except LocalInferenceError as exc:
            recovery = (
                correction
                + " The previous response was not valid JSON. Return exactly one JSON object with keys action, "
                "reason, risk, expected_files, and patch_recipe_hypothesis. Do not include analysis text."
            )
            try:
                payload = caller([messages[0], {"role": "user", "content": recovery}], config=config)
            except LocalInferenceError as retry_exc:
                target_results.append(
                    {
                        "target": target,
                        "status": "unavailable",
                        "schema_retry_attempted": True,
                        "error": str(retry_exc or exc)[:160],
                    }
                )
                diagnostic.update({"status": "decomposition_failed", "target_results": target_results})
                return None
        recipe = normalize_recipe(payload)
        errors = candidate_errors(
            recipe,
            target,
            str(change.get("source_excerpt") or ""),
            allowed_targets=[target],
            source_excerpts={target: str(change.get("source_excerpt") or "")},
        )
        if payload.get("action") != "propose_patch_recipe":
            errors.append("target_recipe_not_proposed")
        replacement = _replacement_for_target(recipe, target)
        if not replacement:
            errors.append("missing_target_replacement_source")
        target_results.append({"target": target, "status": "accepted" if not errors else "rejected", "errors": errors})
        if errors or not replacement:
            diagnostic.update({"status": "decomposition_failed", "target_results": target_results})
            return None
        edits.append({"target_symbol": target, "replacement_source": replacement, "summary": recipe.get("summary")})
    diagnostic.update({"status": "decomposed", "result_action": "propose_patch_recipe", "target_results": target_results})
    return {
        "action": "propose_patch_recipe",
        "reason": "composite candidate assembled from bounded target proposals",
        "risk": "atomic verifier must accept every target proposal",
        "expected_files": sorted({str(item.get("target") or "").split(":", 1)[0] for item in changes}),
        "patch_recipe_hypothesis": {
            "recipe_type": "decomposed_composite_repair",
            "target_symbol": str(evidence.get("target") or ""),
            "edit_format": "replace_functions",
            "edits": edits,
            "summary": "bounded per-target composite candidate",
            "verification_hint": "apply atomically and rerun all acceptance obligations",
        },
    }


def _replacement_for_target(recipe: dict[str, Any], target: str) -> str:
    replacement = str(recipe.get("replacement_source") or "")
    if replacement:
        return replacement
    for edit in list(recipe.get("edits") or []):
        if str(dict(edit).get("target_symbol") or "") == target:
            return str(dict(edit).get("replacement_source") or "")
    return ""
