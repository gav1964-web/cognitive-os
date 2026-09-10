"""Unified Cognitive OS entrypoint and route dispatcher."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .greenfield_role_pipeline import run_greenfield_role_pipeline
from .llm_gateway_bootstrap import ensure_llm_gateway
from .prompt_adequacy import evaluate_prompt_adequacy
from .role_foundation_pipeline import run_role_foundation_pipeline
from .stage2_template_routes import select_stage2_case
from .verified_system_package import build_verified_system_package


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "cognitive_os_entry_routes.json"


class CognitiveOSEntryRoutesError(RuntimeError):
    """Raised when the unified entry route configuration is invalid."""


@lru_cache(maxsize=1)
def load_cognitive_os_entry_routes(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else ROUTES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "cognitive_os_entry_routes.v1":
        raise CognitiveOSEntryRoutesError("entry routes must use schema_version cognitive_os_entry_routes.v1")
    if payload.get("status") != "active":
        raise CognitiveOSEntryRoutesError("entry routes must be active")
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise CognitiveOSEntryRoutesError("routes must be a non-empty list")
    pipelines = set(dict(payload.get("pipeline_contracts") or {}).keys())
    for row in routes:
        if not isinstance(row, dict) or str(row.get("pipeline") or "") not in pipelines:
            raise CognitiveOSEntryRoutesError("each route must reference a declared pipeline contract")
    return payload


def run_cognitive_os(
    *,
    root: Path,
    prompt: str,
    project_dir: Path | None = None,
    output_dir: Path | None = None,
    mode: str = "auto",
    write: bool = False,
    use_l45_model: bool = False,
    question_mode: str = "continue_with_assumptions",
) -> dict[str, Any]:
    root = root.resolve()
    decision = decide_entry_route(root=root, prompt=prompt, project_dir=project_dir, mode=mode)
    gateway = ensure_llm_gateway(root)
    if gateway["status"] == "failed":
        result = {"status": "blocked", "error": gateway.get("error", "LLM gateway unavailable")}
        return _entry_report(prompt, decision, result, write=write, root=root, gateway=gateway)
    pipeline = decision["pipeline"]
    if pipeline == "project_foundation_analysis":
        if project_dir is None:
            return _entry_report(
                prompt, decision, {"status": "blocked", "error": "project_dir is required"},
                write=write, root=root, gateway=gateway,
            )
        result = run_role_foundation_pipeline(root=root, project_dir=project_dir.resolve(), goal=prompt, write=write)
    elif pipeline == "prompt_to_product":
        result = build_verified_system_package(
            root=root,
            prompt=prompt,
            curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
            write=write,
            output_dir=output_dir,
            use_l45_model=use_l45_model,
        )
    elif pipeline == "greenfield_architect_spec":
        result = run_greenfield_role_pipeline(
            root=root,
            prompt=prompt,
            write=write,
            question_mode=question_mode,
            use_l45_model=use_l45_model,
        )
    else:
        result = _clarification_result(prompt, decision)
    return _entry_report(prompt, decision, result, write=write, root=root, gateway=gateway)


def decide_entry_route(*, root: Path, prompt: str, project_dir: Path | None = None, mode: str = "auto") -> dict[str, Any]:
    routes = load_cognitive_os_entry_routes()
    prompt_adequacy = evaluate_prompt_adequacy(prompt).to_dict()
    stage2_case = select_stage2_case(prompt)
    evidence = {
        "mode": mode,
        "project_dir": project_dir.as_posix() if project_dir else None,
        "project_dir_exists": bool(project_dir and project_dir.exists()),
        "prompt_adequacy_status": prompt_adequacy.get("status"),
        "system_type": prompt_adequacy.get("system_type"),
        "stage2_case": stage2_case,
    }
    for route in sorted(routes["routes"], key=lambda row: int(row.get("priority", 100))):
        if _route_matches(route, prompt=prompt, mode=mode, evidence=evidence):
            return {
                "artifact_type": "CognitiveOSEntryRouteDecision",
                "status": "decided",
                "created_at": _now(),
                "route_id": route["route_id"],
                "pipeline": route["pipeline"],
                "pipeline_contract": dict(routes["pipeline_contracts"]).get(route["pipeline"]),
                "prompt_adequacy": prompt_adequacy,
                "stage2_case": stage2_case,
                "evidence": evidence,
            }
    default_pipeline = str(routes.get("default_route") or "prompt_to_product")
    return {
        "artifact_type": "CognitiveOSEntryRouteDecision",
        "status": "decided",
        "created_at": _now(),
        "route_id": default_pipeline,
        "pipeline": default_pipeline,
        "pipeline_contract": dict(routes["pipeline_contracts"]).get(default_pipeline),
        "prompt_adequacy": prompt_adequacy,
        "stage2_case": stage2_case,
        "evidence": evidence,
    }


def _route_matches(route: dict[str, Any], *, prompt: str, mode: str, evidence: dict[str, Any]) -> bool:
    lower = prompt.lower()
    if route.get("requires_project_dir") and not evidence["project_dir_exists"]:
        return False
    if route.get("requires_stage2_template") and not evidence["stage2_case"]:
        return False
    statuses = [str(item) for item in route.get("prompt_statuses", [])]
    if statuses and str(evidence["prompt_adequacy_status"]) not in statuses:
        return False
    mode_markers = [str(item) for item in route.get("mode_markers", [])]
    if mode_markers and mode not in mode_markers and mode != str(route.get("pipeline")):
        return False
    markers = [str(item) for item in route.get("intent_markers", [])]
    if markers and not any(marker in lower for marker in markers):
        return False
    return True


def _clarification_result(prompt: str, decision: dict[str, Any]) -> dict[str, Any]:
    gate = dict(decision.get("prompt_adequacy") or {})
    return {
        "artifact_type": "ClarificationPacket",
        "status": "needs_clarification",
        "prompt": prompt,
        "questions": gate.get("clarification_questions", []),
        "missing": gate.get("missing", []),
        "reason_code": gate.get("reason_code"),
    }


def _entry_report(
    prompt: str, decision: dict[str, Any], result: dict[str, Any], *,
    write: bool, root: Path, gateway: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "artifact_type": "CognitiveOSEntryRunReport",
        "status": "ok" if result.get("status") in {"ok", "needs_clarification", "needs_improvement"} else "blocked",
        "created_at": _now(),
        "prompt": prompt,
        "route_decision": decision,
        "pipeline_result": result,
        "llm_gateway": dict(gateway or {"status": "not_checked"}),
        "invariants": {
            "single_entrypoint_used": True,
            "route_selected_by_config": True,
            "direct_user_source_modification": False,
            "llm_gateway_bootstrap_recorded": True,
        },
    }
    if write:
        out_dir = root / "artifacts" / "cognitive_os_entry"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"cognitive_os_entry_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
