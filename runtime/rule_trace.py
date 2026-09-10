"""Build compact traces that explain config-driven runtime decisions."""

from __future__ import annotations

from typing import Any


def build_rule_trace(report: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    gate = dict(report.get("prompt_adequacy") or {})
    if gate:
        steps.append(
            {
                "layer": "L4",
                "source": "config/prompt_intake_rules.json",
                "decision": f"prompt_adequacy:{gate.get('status')}",
                "evidence": {
                    "system_type": gate.get("system_type"),
                    "missing": gate.get("missing"),
                },
            }
        )
    control = dict(report.get("cognitive_control_plane") or {})
    transition = dict(control.get("role_transition") or {})
    if transition:
        steps.append(
            {
                "layer": "L4",
                "source": "config/l4_decision_rules.json",
                "rule_id": transition.get("rule_id"),
                "decision": transition.get("next_action"),
                "evidence": {"reason_code": transition.get("reason_code")},
            }
        )
    selected_case = report.get("selected_case") or _case_from_project(report)
    if selected_case:
        steps.append(
            {
                "layer": "L4",
                "source": "config/stage2_template_routes.json",
                "decision": "select_stage2_case",
                "evidence": {"case": selected_case},
            }
        )
    semantic = dict(report.get("semantic_hypothesis_proposal") or {})
    if semantic:
        proposal = dict(semantic.get("proposal") or {})
        steps.append(
            {
                "layer": "L4.5",
                "source": "config/semantic_resolution_rules.json + optional bounded LLM hypothesis",
                "rule_id": proposal.get("rule_id") or proposal.get("resolution_id"),
                "decision": semantic.get("hypothesis_type") or proposal.get("type"),
                "evidence": {"status": semantic.get("status"), "confidence": proposal.get("confidence")},
            }
        )
    sandbox = dict(report.get("llm_sandbox_implementation") or {})
    implementation_plan = dict(sandbox.get("implementation_plan") or {})
    recipe = dict(implementation_plan.get("operation_recipe") or {})
    if recipe:
        steps.append(
            {
                "layer": "L4.5",
                "source": "config/operation_recipe_rules.json + registry/interface_contracts.json",
                "decision": "operation_recipe_selected",
                "evidence": {
                    "interface_contract": recipe.get("interface_contract"),
                    "transform": recipe.get("transform"),
                    "source": recipe.get("source"),
                },
            }
        )
    if sandbox:
        route = dict(sandbox.get("route_resolution") or {})
        steps.append(
            {
                "layer": "L4.5",
                "source": "registry/sandbox_programmer_operations.json + config/sandbox_programmer_profiles.json",
                "decision": route.get("strategy"),
                "evidence": {
                    "status": route.get("status"),
                    "operation": route.get("candidate_operation_id"),
                    "model_invoked": route.get("model_invoked"),
                },
            }
        )
    if report.get("programmer_sandbox_gate") or report.get("generated_package_evaluation"):
        steps.append(
            {
                "layer": "Release",
                "source": "config/sandbox_release_policy.json",
                "decision": dict(report.get("release_decision") or {}).get("decision"),
                "evidence": {"status": report.get("status")},
            }
        )
    return {
        "artifact_type": "RuleTrace",
        "status": "ok",
        "step_count": len(steps),
        "steps": steps,
    }


def _case_from_project(report: dict[str, Any]) -> str | None:
    project_dir = str(report.get("project_dir") or "")
    if not project_dir:
        return None
    return project_dir.rstrip("/\\").split("/")[-1] or None
