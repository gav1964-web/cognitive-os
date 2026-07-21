"""Typed sandbox attempt contract for L4.5-to-Stage-2 fallback execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapter_implementation_plan import build_adapter_implementation_plan_from_conversion
from .generic_file_conversion_recipe import build_conversion_recipe
from .library_binding_recipe import build_library_binding_recipe_from_conversion


DEFAULT_POLICY = {
    "artifact_type": "SandboxAttemptPolicy",
    "schema_version": "0.1",
    "status": "fallback_default",
    "allowed_attempt_kinds": {
        "existing_stage2_case": {
            "cases": ["csv_sort_cli", "image_contents_cli"],
            "requires_curriculum_reference": True,
        },
        "bounded_adapter_recipe": {
            "cases": ["generic_file_converter_cli"],
            "requires_curriculum_reference": False,
            "allowed_backend_prefixes": ["stdlib_"],
            "allowed_backends": ["fixture_adapter"],
            "required_artifacts": [
                "GenericFileConversionRecipe",
                "LibraryBindingRecipe",
                "AdapterImplementationPlan",
            ],
        },
    },
    "runner": {"allowed": ["ProgrammerProjectReview"]},
    "verification_commands": ["python -m compileall -b .", "python -m pytest tests -q"],
    "allowed_operations": [
        "create_isolated_scaffold",
        "write_generated_package_files",
        "write_recipe_artifacts",
        "select_existing_adapter_backend",
        "run_project_scoped_compileall",
        "run_project_scoped_pytest",
        "read_project_scoped_verification",
    ],
    "forbidden_operations": [
        "edit_user_source_tree",
        "mutate_registry",
        "promote_kb_candidate",
        "install_dependencies",
        "call_network",
        "execute_model_generated_code",
        "run_arbitrary_shell",
    ],
    "required_true_invariants": [
        "sandbox_only",
        "existing_case_or_bounded_adapter_recipe_only",
        "project_scoped_verification_required",
        "llm_output_is_not_executed",
    ],
    "required_false_invariants": ["source_tree_changes", "registry_changes", "kb_promotion"],
}


def build_sandbox_attempt_spec(
    *,
    prompt: str,
    semantic_proposal: dict[str, Any],
    case_name: str | None,
    curriculum_dir: Path,
) -> dict[str, Any]:
    policy = load_sandbox_attempt_policy(curriculum_dir.parent.parent if curriculum_dir.name else Path("."))
    proposal = dict(semantic_proposal.get("proposal") or {})
    kind = "bounded_adapter_recipe" if case_name in _allowed_cases(policy, "bounded_adapter_recipe") else "existing_stage2_case"
    recipe = build_conversion_recipe(prompt) if kind == "bounded_adapter_recipe" else None
    binding = build_library_binding_recipe_from_conversion(recipe).to_dict() if recipe is not None else None
    adapter_plan = build_adapter_implementation_plan_from_conversion(recipe).to_dict() if recipe is not None else None
    spec = {
        "artifact_type": "SandboxAttemptSpec",
        "schema_version": "0.1",
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "source": {
            "artifact_type": semantic_proposal.get("artifact_type"),
            "hypothesis_type": semantic_proposal.get("hypothesis_type"),
            "resolution_id": proposal.get("resolution_id"),
            "evidence_refs": list(semantic_proposal.get("evidence_refs") or []),
        },
        "policy": {
            "source": policy.get("_source", "default"),
            "status": policy.get("status"),
            "schema_version": policy.get("schema_version"),
        },
        "attempt": {
            "kind": kind,
            "case_name": case_name,
            "runner": "ProgrammerProjectReview",
            "curriculum_reference": f"{case_name}/teacher_reference.json" if case_name else None,
            "verification_commands": list(policy.get("verification_commands") or DEFAULT_POLICY["verification_commands"]),
            "recipe": recipe.to_dict() if recipe is not None else None,
            "library_binding_recipe": binding,
            "adapter_implementation_plan": adapter_plan,
        },
        "allowed_operations": list(policy.get("allowed_operations") or DEFAULT_POLICY["allowed_operations"]),
        "forbidden_operations": list(policy.get("forbidden_operations") or DEFAULT_POLICY["forbidden_operations"]),
        "invariants": {
            "sandbox_only": True,
            "existing_case_or_bounded_adapter_recipe_only": True,
            "project_scoped_verification_required": True,
            "source_tree_changes": False,
            "registry_changes": False,
            "kb_promotion": False,
            "llm_output_is_not_executed": True,
        },
    }
    validation = validate_sandbox_attempt_spec(spec=spec, curriculum_dir=curriculum_dir, policy=policy)
    spec["validation"] = validation
    spec["status"] = "ready" if validation["status"] == "ok" else "blocked"
    return spec


def load_sandbox_attempt_policy(root: Path) -> dict[str, Any]:
    source = root / "registry" / "sandbox_attempt_policy.json"
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = dict(DEFAULT_POLICY)
        payload["_source"] = "fallback_default"
        return payload
    if payload.get("artifact_type") != "SandboxAttemptPolicy" or payload.get("status") != "active":
        payload = dict(DEFAULT_POLICY)
        payload["_source"] = "fallback_default_invalid_registry"
        return payload
    payload["_source"] = source.as_posix()
    return payload


def validate_sandbox_attempt_spec(
    *,
    spec: dict[str, Any],
    curriculum_dir: Path,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = dict(policy or load_sandbox_attempt_policy(curriculum_dir.parent.parent if curriculum_dir.name else Path(".")))
    violations: list[str] = []
    attempt = dict(spec.get("attempt") or {})
    invariants = dict(spec.get("invariants") or {})
    forbidden = set(str(item) for item in spec.get("forbidden_operations") or [])
    allowed = set(str(item) for item in spec.get("allowed_operations") or [])
    case_name = str(attempt.get("case_name") or "")
    if spec.get("artifact_type") != "SandboxAttemptSpec":
        violations.append("artifact_type_must_be_SandboxAttemptSpec")
    if attempt.get("kind") != "existing_stage2_case":
        if attempt.get("kind") != "bounded_adapter_recipe":
            violations.append("attempt_kind_must_be_existing_stage2_case_or_bounded_adapter_recipe")
    if attempt.get("kind") == "existing_stage2_case" and case_name not in _allowed_cases(policy, "existing_stage2_case"):
        violations.append(f"case_not_allowlisted:{case_name or '<missing>'}")
    if attempt.get("kind") == "bounded_adapter_recipe":
        if case_name not in _allowed_cases(policy, "bounded_adapter_recipe"):
            violations.append(f"bounded_adapter_case_not_allowlisted:{case_name or '<missing>'}")
        recipe = dict(attempt.get("recipe") or {})
        binding = dict(attempt.get("library_binding_recipe") or {})
        adapter_plan = dict(attempt.get("adapter_implementation_plan") or {})
        if recipe.get("artifact_type") != "GenericFileConversionRecipe":
            violations.append("bounded_adapter_recipe_missing_conversion_recipe")
        if binding.get("artifact_type") != "LibraryBindingRecipe":
            violations.append("bounded_adapter_recipe_missing_library_binding_recipe")
        if adapter_plan.get("artifact_type") != "AdapterImplementationPlan":
            violations.append("bounded_adapter_recipe_missing_adapter_implementation_plan")
        if dict(binding.get("authority") or {}).get("may_install_dependencies") is not False:
            violations.append("bounded_adapter_may_not_install_dependencies")
        if dict(binding.get("authority") or {}).get("may_call_network") is not False:
            violations.append("bounded_adapter_may_not_call_network")
        if dict(adapter_plan.get("authority") or {}).get("may_edit_user_source") is not False:
            violations.append("bounded_adapter_may_not_edit_user_source")
        selected_backend = str(adapter_plan.get("selected_backend") or "")
        if not selected_backend:
            violations.append("bounded_adapter_selected_backend_required")
        if not _backend_allowed(policy, selected_backend):
            violations.append(f"bounded_adapter_backend_not_allowlisted:{selected_backend}")
    reference = curriculum_dir / case_name / "teacher_reference.json"
    if case_name and not reference.is_file() and _requires_curriculum_reference(policy, str(attempt.get("kind") or "")):
        violations.append(f"curriculum_reference_missing:{case_name}")
    allowed_runners = set(str(item) for item in dict(policy.get("runner") or {}).get("allowed") or [])
    if attempt.get("runner") not in allowed_runners:
        violations.append("runner_must_be_ProgrammerProjectReview")
    commands = [str(item) for item in attempt.get("verification_commands") or []]
    if commands != [str(item) for item in policy.get("verification_commands") or []]:
        violations.append("verification_commands_must_be_project_scoped_compileall_and_pytest")
    required_allowed = set(str(item) for item in policy.get("allowed_operations") or [])
    if not required_allowed.issubset(allowed):
        violations.append("missing_required_allowed_operations")
    required_forbidden = set(str(item) for item in policy.get("forbidden_operations") or [])
    if not required_forbidden.issubset(forbidden):
        violations.append("missing_required_forbidden_operations")
    for key in [str(item) for item in policy.get("required_true_invariants") or []]:
        if invariants.get(key) is not True:
            violations.append(f"invariant_must_be_true:{key}")
    for key in [str(item) for item in policy.get("required_false_invariants") or []]:
        if invariants.get(key) is not False:
            violations.append(f"invariant_must_be_false:{key}")
    return {
        "artifact_type": "SandboxAttemptSpecValidation",
        "status": "blocked" if violations else "ok",
        "violations": violations,
        "case_name": case_name or None,
        "policy_source": policy.get("_source", "default"),
        "policy": "Only allowlisted existing Stage 2 cases or bounded adapter recipes may be attempted in sandbox.",
    }


def _allowed_cases(policy: dict[str, Any], kind: str) -> set[str]:
    item = dict(dict(policy.get("allowed_attempt_kinds") or {}).get(kind) or {})
    return {str(case) for case in item.get("cases") or []}


def _requires_curriculum_reference(policy: dict[str, Any], kind: str) -> bool:
    item = dict(dict(policy.get("allowed_attempt_kinds") or {}).get(kind) or {})
    return item.get("requires_curriculum_reference") is True


def _backend_allowed(policy: dict[str, Any], backend: str) -> bool:
    item = dict(dict(policy.get("allowed_attempt_kinds") or {}).get("bounded_adapter_recipe") or {})
    exact = {str(value) for value in item.get("allowed_backends") or []}
    prefixes = [str(value) for value in item.get("allowed_backend_prefixes") or []]
    return backend in exact or any(backend.startswith(prefix) for prefix in prefixes)
