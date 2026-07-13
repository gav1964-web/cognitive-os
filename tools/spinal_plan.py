"""Run a Layer 3.5 spinal planning probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--intent", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--route-goal", default="")
    parser.add_argument("--allow-local-llm", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.layer_packets import intent_packet
    from runtime.registry import CapabilityRegistry
    from runtime.spinal_planner import plan_from_intent_packet
    from runtime.spinal_quality import score_spinal_result

    registry = CapabilityRegistry(root)
    registry.reset_from_plugins(reason="spinal_plan_probe")
    packet = intent_packet(
        correlation_id="spinal_probe",
        intent=args.intent,
        objective=args.objective,
        constraints={"route_goal": args.route_goal} if args.route_goal else {},
        expected_artifacts=["Pipeline", "MotorPlanPacket", "SignalPacket"],
        success_criteria=["validated pipeline or bounded escalation"],
    )
    result = plan_from_intent_packet(packet, registry, allow_local_llm=args.allow_local_llm)
    result["quality"] = score_spinal_result(result, registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["quality"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
