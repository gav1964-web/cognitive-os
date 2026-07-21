"""Evidence packing for bounded L4.5 semantic requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_semantic_evidence_pack(
    *,
    control_plane_decision: dict[str, Any],
    prompt: str | None = None,
    prompt_adequacy: dict[str, Any] | None = None,
    supported_templates: list[str] | None = None,
    known_templates: list[str] | None = None,
    role_artifacts: dict[str, dict[str, Any]] | None = None,
    failed_gates: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact fact packet for L4.5 without granting execution authority."""

    decision = dict(control_plane_decision)
    semantic_escalation = dict(decision.get("semantic_escalation", {}))
    prompt_product_gate = dict(decision.get("prompt_product_gate", {}))
    artifact_gate = dict(decision.get("artifact_promotion_gate", {}))
    return {
        "artifact_type": "SemanticEvidencePack",
        "layer": "L4.0",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_facts": {
            "prompt": prompt,
            "prompt_adequacy": dict(prompt_adequacy or decision.get("prompt_adequacy", {})),
            "supported_template": prompt_product_gate.get("supported_template"),
            "known_templates": list(known_templates or []),
            "supported_templates": list(supported_templates or []),
        },
        "control_facts": {
            "decision_artifact_type": decision.get("artifact_type"),
            "mode": decision.get("mode"),
            "role_transition": dict(decision.get("role_transition", {})),
            "semantic_escalation": semantic_escalation,
            "prompt_product_gate": prompt_product_gate,
            "artifact_promotion_gate": artifact_gate,
            "failed_gates": list(failed_gates or _failed_gate_checks(prompt_product_gate, artifact_gate)),
        },
        "role_artifact_facts": _summarize_role_artifacts(role_artifacts or {}),
        "forbidden_actions": [
            "execute_pipeline",
            "edit_user_source_tree",
            "mutate_registry",
            "build_package",
            "promote_capability",
            "bypass_prompt_product_gate",
            "bypass_artifact_promotion_gate",
        ],
        "context": dict(context or {}),
        "authority": {
            "may_execute": False,
            "may_edit_source": False,
            "may_mutate_registry": False,
            "may_build_package": False,
            "must_return_to": "L4.0",
        },
    }


def _failed_gate_checks(*gates: dict[str, Any]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for gate in gates:
        for check in gate.get("checks", []):
            if isinstance(check, dict) and not check.get("passed", False):
                failed.append(
                    {
                        "code": check.get("code"),
                        "actual": check.get("actual"),
                        "gate_status": gate.get("status"),
                    }
                )
    return failed


def _summarize_role_artifacts(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            continue
        summary[name] = {
            "artifact_type": artifact.get("artifact_type"),
            "status": artifact.get("status"),
            "recommendation": artifact.get("recommendation"),
            "chosen_option": artifact.get("chosen_option"),
            "target": _first_present(
                artifact,
                ["implementation_target", "test_target", "candidate", "selected_candidate"],
            ),
        }
    return summary


def _first_present(artifact: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in artifact:
            return artifact[key]
    return None
