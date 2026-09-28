"""Bounded fallback autonomy loop for Stage 2 prompt-to-product."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .generic_file_conversion_recipe import build_conversion_recipe
from .greenfield_generic_file_converter_template import expected_artifacts as generic_converter_expected_artifacts
from .knowledge_admission import build_kb_candidate, write_kb_candidate
from .programmer_project_review import run_programmer_project_review
from .sandbox_attempt_spec import build_sandbox_attempt_spec


def run_fallback_autonomy_loop(
    *,
    root: Path,
    curriculum_dir: Path,
    prompt: str,
    semantic_proposal: dict[str, Any] | None,
    semantic_validation: dict[str, Any] | None,
    write: bool,
) -> dict[str, Any]:
    loop = {
        "artifact_type": "FallbackAutonomyLoop",
        "status": "not_attempted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "steps": [],
        "invariants": {
            "sandbox_only": True,
            "llm_may_propose_not_execute": True,
            "source_tree_changes": False,
            "registry_changes": False,
            "kb_promotion": False,
        },
    }
    proposal = dict(semantic_proposal or {})
    validation = dict(semantic_validation or {})
    if validation.get("accepted_action") != "record_successful_resolution_candidate":
        loop["status"] = "developer_handoff_required"
        loop["steps"].append(
            {
                "step": "l45_existing_means_check",
                "status": "no_verified_existing_route",
                "reason": validation.get("accepted_action") or "no_valid_semantic_proposal",
            }
        )
        return loop
    case_name = _case_from_successful_resolution(proposal)
    if case_name is None:
        loop["status"] = "developer_handoff_required"
        loop["steps"].append(
            {
                "step": "route_mapping",
                "status": "blocked",
                "reason": "successful resolution did not map to an executable sandbox case",
            }
        )
        return loop
    loop["steps"].append({"step": "route_mapping", "status": "ok", "case": case_name})
    attempt_spec = build_sandbox_attempt_spec(
        prompt=prompt,
        semantic_proposal=proposal,
        case_name=case_name,
        curriculum_dir=curriculum_dir,
    )
    loop["sandbox_attempt_spec"] = attempt_spec
    loop["steps"].append(
        {
            "step": "sandbox_attempt_spec_validation",
            "status": attempt_spec["validation"]["status"],
            "case": case_name,
        }
    )
    if attempt_spec["status"] != "ready":
        loop["status"] = "developer_handoff_required"
        loop["result"] = "sandbox attempt spec failed validation"
        return loop
    try:
        review_run = run_programmer_project_review(
            root=root,
            curriculum_dir=curriculum_dir,
            case_name=str(attempt_spec["attempt"]["case_name"]),
            write=write,
            reference_override=_reference_override_for_attempt(prompt, attempt_spec),
        )
    except Exception as exc:
        loop["status"] = "developer_handoff_required"
        loop["steps"].append({"step": "sandbox_attempt", "status": "failed", "error": str(exc)})
        return loop
    loop["sandbox_attempt"] = review_run
    loop["steps"].append({"step": "sandbox_attempt", "status": review_run.get("status"), "case": case_name})
    if review_run.get("status") == "ok":
        loop["status"] = "sandbox_verified"
        loop["selected_case"] = case_name
        loop["result"] = "existing route verified in sandbox"
        candidate = _successful_resolution_kb_candidate(
            prompt=prompt,
            case_name=case_name,
            semantic_proposal=proposal,
            attempt_spec=attempt_spec,
            review_run=review_run,
        )
        loop["knowledge_candidate"] = candidate
        if write:
            loop["knowledge_candidate_path"] = write_kb_candidate(candidate, root=root).as_posix()
    else:
        loop["status"] = "developer_handoff_required"
        loop["result"] = "existing route failed verification"
        loop["developer_improvement_request"] = _developer_improvement_request(prompt, case_name, review_run)
    return loop


def _reference_override_for_attempt(prompt: str, attempt_spec: dict[str, Any]) -> dict[str, Any] | None:
    attempt = dict(attempt_spec.get("attempt") or {})
    if attempt.get("kind") != "bounded_adapter_recipe":
        return None
    case_name = str(attempt.get("case_name") or "")
    if case_name != "generic_file_converter_cli":
        return None
    recipe = build_conversion_recipe(prompt)
    if recipe is None:
        return None
    return {
        "artifact_type": "TeacherReference",
        "case": case_name,
        "teacher_reference_not_ground_truth": True,
        "prompt": prompt,
        "expected_artifacts": generic_converter_expected_artifacts(prompt),
        "acceptance_criteria": [
            "conversion recipe captures source and target formats",
            "library binding recipe proposes bounded adapter candidates",
            "adapter implementation plan selects implemented stdlib backend or fallback",
            "CLI writes target output through adapter boundary",
            "missing or unsupported inputs are rejected with controlled errors",
            "default tests run without real conversion dependencies or network",
            "all tests run from generated project root",
        ],
        "recipe": recipe.to_dict(),
    }


def _case_from_successful_resolution(proposal: dict[str, Any]) -> str | None:
    data = dict(proposal.get("proposal") or {})
    for item in data.get("means_used") or []:
        marker = str(item)
        if marker.startswith("known_template:"):
            return marker.split(":", 1)[1]
    return None


def _successful_resolution_kb_candidate(
    *,
    prompt: str,
    case_name: str,
    semantic_proposal: dict[str, Any],
    attempt_spec: dict[str, Any],
    review_run: dict[str, Any],
) -> dict[str, Any]:
    data = dict(semantic_proposal.get("proposal") or {})
    proposed_record = {
        "record_type": "successful_resolution_candidate",
        "rule_id": f"stage2_route_{case_name}",
        "label": f"Stage 2 prompt can route to {case_name}",
        "role_scope": ["researcher", "implementer", "tester", "reviewer"],
        "prompt_pattern": prompt,
        "route": {
            "case_name": case_name,
            "resolution_id": data.get("resolution_id"),
            "means_used": list(data.get("means_used") or []),
        },
        "sandbox_attempt": {
            "status": attempt_spec.get("status"),
            "kind": dict(attempt_spec.get("attempt") or {}).get("kind"),
        },
        "verification": {
            "status": review_run.get("status"),
            "project_dir": dict(review_run.get("programmer_artifact", {})).get("project_dir"),
        },
    }
    return build_kb_candidate(
        record_type="successful_resolution_candidate",
        proposed_record=proposed_record,
        source_cases=[
            {
                "status": "verified",
                "prompt": prompt,
                "case_name": case_name,
                "sandbox_status": review_run.get("status"),
            }
        ],
        teacher_reference="fallback_autonomy_loop_sandbox_verification",
        teacher_approved=False,
        codex_approved=False,
    )


def _developer_improvement_request(prompt: str, case_name: str, review_run: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "DeveloperImprovementRequest",
        "status": "requested",
        "prompt": prompt,
        "case_name": case_name,
        "reason": "fallback route existed but failed sandbox verification",
        "failed_review_status": review_run.get("status"),
        "required_next_step": "developer inspects failed sandbox, adds deterministic template/policy/tests, then reruns",
        "automatic_code_change_allowed": False,
    }
