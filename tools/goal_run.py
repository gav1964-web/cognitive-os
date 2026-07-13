"""Run a human goal through Level 4 -> Level 3.5 -> Runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

LOCAL_L4_FORBIDDEN_MODELS = {
    "local",
    "qwen-local",
    "qwen-local-cpu",
    "fast-local-cpu",
    "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--goal", default=None)
    parser.add_argument("--goal-id", default=None)
    parser.add_argument("--clarification", default=None)
    parser.add_argument("--input-json", default="{}")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--use-l4-llm", action="store_true")
    parser.add_argument("--interpret-project-llm", action="store_true")
    parser.add_argument("--dialogue-id", default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="local")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--no-response-format", action="store_true")
    parser.add_argument("--l4-base-url", default=os.environ.get("COGNITIVE_OS_L4_BASE_URL")); parser.add_argument("--l4-model", default=os.environ.get("COGNITIVE_OS_L4_MODEL"))
    parser.add_argument("--l4-timeout", type=float, default=float(os.environ.get("COGNITIVE_OS_L4_TIMEOUT", "120"))); parser.add_argument("--l4-api-key-env", default=os.environ.get("COGNITIVE_OS_L4_API_KEY_ENV", "COGNITIVE_OS_L4_API_KEY"))
    parser.add_argument("--l4-no-response-format", action="store_true")
    parser.add_argument("--l4-context", choices=["expanded", "compact"], default=os.environ.get("COGNITIVE_OS_L4_CONTEXT", "expanded"))
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    root = Path(args.root).resolve()

    from tools.goal_packet_helpers import (
        expected_artifacts,
        intent_for_decision,
        is_project_analysis,
        success_criteria,
    )
    from runtime.dialogue_memory import DialogueMemory
    from runtime.goal_intake import build_goal_spec
    from runtime.goal_orchestrator import decide_goal_route, decide_goal_route_with_llm
    from runtime.goal_report import build_goal_report
    from runtime.goal_runtime import execute_motor_route, plan_motor_route
    from runtime.goal_session import GoalSessionStore
    from runtime.knowledge import apply_knowledge_route_override, knowledge_preflight
    from runtime.level4_deliberation import build_deliberation
    from runtime.layer_packets import intent_packet, signal_packet
    from runtime.local_inference import LocalInferenceConfig
    from runtime.memory_index import MemoryIndex
    from runtime.project_deliberation import deliberate_project_report
    from runtime.project_signals import generate_project_signals
    from runtime.project_tasks import generate_project_tasks
    from runtime.registry import CapabilityRegistry

    registry = CapabilityRegistry(root)
    registry.load()
    store = GoalSessionStore(root)
    root_input = json.loads(args.input_json)
    if not isinstance(root_input, dict):
        print(json.dumps({"status": "failed", "error": "--input-json must decode to object"}, ensure_ascii=True, indent=2))
        return 2
    if args.goal_id:
        session = store.load(args.goal_id)
        root_input = dict(session.get("root_input") or root_input)
        if args.clarification:
            store.add_clarification(session, args.clarification)
    else:
        if not args.goal:
            print(json.dumps({"status": "failed", "error": "--goal is required when --goal-id is not provided"}, ensure_ascii=True, indent=2))
            return 2
        session = store.create(args.goal, root_input=root_input)
    goal = str(session.get("effective_goal") or session["goal"])
    dialogue_preflight = None
    if args.dialogue_id:
        dialogue_memory = DialogueMemory(root)
        dialogue_memory.add_turn(args.dialogue_id, role="user", content=goal)
        dialogue_preflight = {
            "dialogue_id": args.dialogue_id,
            "recall": dialogue_memory.recall(goal, limit=3),
            "summary": dialogue_memory.summary(dialogue_id=args.dialogue_id, limit=5),
        }
        store.append_event(
            session,
            "dialogue_preflight",
            {
                "dialogue_id": args.dialogue_id,
                "match_count": len(dialogue_preflight["recall"].get("matches", [])),
                "active_topic": dialogue_preflight["summary"].get("active_topic"),
            },
        )
    memory_index = MemoryIndex(root)
    memory_preflight = memory_index.search(goal, limit=3)
    goal_spec = build_goal_spec(goal, root_input=root_input)
    store.append_event(
        session,
        "goal_intake",
        {
            "status": goal_spec.status,
            "intent": goal_spec.intent,
            "target": goal_spec.target,
            "ambiguity_score": goal_spec.ambiguity_score,
        },
    )
    store.append_event(
        session,
        "memory_preflight",
        {
            "recommendation": memory_preflight.get("recommendation"),
            "template_recommendation": memory_preflight.get("template_recommendation"),
            "match_count": len(memory_preflight.get("matches", [])),
            "template_match_count": len(memory_preflight.get("template_matches", [])),
        },
    )
    knowledge = knowledge_preflight(goal, root_input)
    store.append_event(
        session,
        "knowledge_preflight",
        {
            "status": knowledge.get("status"),
            "gap_count": len(knowledge.get("knowledge_gaps", [])),
            "artifact_count": len(knowledge.get("knowledge_artifacts", [])),
        },
    )
    config = LocalInferenceConfig(base_url=args.base_url.rstrip("/"), model=args.model, timeout_seconds=args.timeout, response_format=not args.no_response_format, provider_label="local")
    cortex_config = _cortex_config(args, LocalInferenceConfig)
    if args.use_l4_llm and cortex_config is not None:
        decision = decide_goal_route_with_llm(goal, registry, root_input=root_input, config=cortex_config)
    else:
        decision = decide_goal_route(goal, registry, root_input=root_input)
        if args.use_l4_llm:
            store.append_event(session, "level4_external_required", {"reason": "L4 LLM requires --l4-model"})
    store.append_event(session, "level4_decision", decision.to_dict())
    overridden = apply_knowledge_route_override(goal, decision, knowledge)
    if overridden is not decision:
        decision = overridden
        store.append_event(session, "level4_decision_overridden_by_knowledge", dict(knowledge.get("route_override") or {}))
    deliberation = build_deliberation(
        goal=goal,
        decision=decision,
        registry=registry,
        memory_preflight=memory_preflight,
        dialogue_preflight=dialogue_preflight,
    )
    store.append_event(
        session,
        "level4_deliberation",
        {
            "route": deliberation["route"],
            "recommendation": deliberation["recommendation"],
            "risk_count": len(deliberation["risks"]),
            "selected_alternative": dict(deliberation.get("selected_alternative") or {}).get("id"),
        },
    )
    intent = intent_packet(
        correlation_id=str(session["goal_id"]),
        intent=intent_for_decision(decision.action),
        objective=goal,
        constraints={
            "risk_posture": "conservative",
            "read_only": is_project_analysis(decision.required_capabilities),
            "execute_requested": bool(args.execute),
            "required_capabilities": list(decision.required_capabilities),
        },
        expected_artifacts=expected_artifacts(decision.required_capabilities),
        success_criteria=success_criteria(decision.required_capabilities),
    )
    report: dict[str, object] = {
        "status": "decided",
        "goal_id": session["goal_id"],
        "goal_intake": goal_spec.to_dict(),
        "dialogue_preflight": dialogue_preflight,
        "memory_preflight": memory_preflight,
        "knowledge_preflight": knowledge,
        "knowledge_gaps": knowledge.get("knowledge_gaps", []),
        "knowledge_artifacts": knowledge.get("knowledge_artifacts", []),
        "level4_decision": decision.to_dict(),
        "level4_deliberation": deliberation,
        "layer_packets": [intent],
    }

    if decision.action != "PLAN_WITH_L35":
        if decision.action == "REQUEST_CAPABILITY_SPEC" and decision.missing_capability_hint:
            spec_path = _write_spec_request(root, decision.missing_capability_hint, goal)
            report["capability_spec_request"] = {"spec": spec_path.as_posix()}
            store.append_event(session, "capability_spec_requested", {"spec": spec_path.as_posix()})
        final_report = build_goal_report(session, report)
        report_path = store.write_report(session, final_report)
        MemoryIndex(root).upsert_report(final_report, report_path)
        report["report_path"] = report_path.as_posix()
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0

    planned = plan_motor_route(
        intent,
        registry,
        required_capabilities=decision.required_capabilities,
        memory_preflight=memory_preflight,
        allow_local_llm=True,
        config=config,
    )

    report["level35_plan"] = planned
    if isinstance(planned.get("motor_plan_packet"), dict):
        report.setdefault("layer_packets", []).append(planned["motor_plan_packet"])
    if isinstance(planned.get("signal_packet"), dict):
        report.setdefault("layer_packets", []).append(planned["signal_packet"])
    if planned.get("status") != "planned":
        report["status"] = "blocked"
        final_report = build_goal_report(session, report)
        report_path = store.write_report(session, final_report)
        MemoryIndex(root).upsert_report(final_report, report_path)
        report["report_path"] = report_path.as_posix()
        store.append_event(session, "level35_blocked", {"errors": planned.get("errors", [])})
        store.save(session)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 2
    store.append_event(session, "level35_planned", {"pipeline_id": planned["pipeline"]["id"]})
    if args.execute:
        motor_run = execute_motor_route(
            root,
            planned,
            root_input,
            registry,
            correlation_id=str(session["goal_id"]),
        )
        report["execution"] = motor_run["execution"]
        report["level35_adaptations"] = motor_run["adaptations"]
        report.setdefault("layer_packets", []).extend(motor_run["layer_packets"])
        store.append_event(session, "executed", {"status": dict(report["execution"]).get("status")})
        if args.interpret_project_llm:
            try:
                report["level35_project_signals"] = generate_project_signals(report, config=config)
                report.setdefault("layer_packets", []).append(
                    signal_packet(
                        correlation_id=str(session["goal_id"]),
                        signals=list(dict(report["level35_project_signals"]).get("signals", [])),
                        needs_l4_decision=False,
                        blocked=False,
                    )
                )
                store.append_event(
                    session,
                    "level35_project_signals",
                    {"status": "ok", "signal_count": len(dict(report["level35_project_signals"]).get("signals", []))},
                )
                report["level4_project_interpretation"] = deliberate_project_report(
                    report,
                    level35_signals=dict(report["level35_project_signals"]),
                    config=cortex_config,
                    context_mode=args.l4_context,
                )
                report["analysis_tasks"] = generate_project_tasks(
                    level35_signals=dict(report["level35_project_signals"]),
                    level4_interpretation=dict(report["level4_project_interpretation"]),
                )
                store.append_event(
                    session,
                    "level4_project_interpreted",
                    {
                        "status": "ok",
                        "provider": cortex_config.provider_label if cortex_config else None,
                        "model": cortex_config.model if cortex_config else None,
                        "context_mode": args.l4_context,
                        "analysis_task_count": dict(report["analysis_tasks"]).get("task_count"),
                    },
                )
            except LocalInferenceError as exc:
                report["level4_project_interpretation"] = {"status": "failed", "error": str(exc)}
                store.append_event(session, "project_interpretation_failed", {"error": str(exc)})
    final_report = build_goal_report(session, report)
    report_path = store.write_report(session, final_report)
    MemoryIndex(root).upsert_report(final_report, report_path)
    report["report_path"] = report_path.as_posix()
    store.save(session)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


def _cortex_config(args: argparse.Namespace, config_cls: type) -> object:
    if not args.l4_model or args.l4_model in LOCAL_L4_FORBIDDEN_MODELS:
        return None
    base_url = (args.l4_base_url or args.base_url).rstrip("/")
    model = args.l4_model
    api_key = os.environ.get(args.l4_api_key_env) if args.l4_api_key_env else None
    return config_cls(
        base_url=base_url,
        model=model,
        timeout_seconds=args.l4_timeout,
        response_format=not args.l4_no_response_format,
        api_key=api_key or None,
        provider_label="external_l4",
    )


def _write_spec_request(root: Path, capability_id: str, goal: str) -> Path:
    path = root / "generated" / "specs" / f"{capability_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = {
        "id": capability_id,
        "purpose": f"Capability requested by Level 4 for goal: {goal}",
        "input_contract": {"value": "string"},
        "output_contract": {"value": "string"},
        "error_policy": {"invalid_input": "raise ValueError"},
        "side_effects": {"filesystem": "none", "network": "none", "secrets": "none"},
        "quality_gate": {"sample_input": {"value": "hello"}, "expected_output": {"value": "hello"}},
        "reusable": True,
    }
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
