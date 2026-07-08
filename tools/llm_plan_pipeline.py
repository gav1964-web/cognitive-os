"""Plan a Pipeline DSL through the local Level 3.5 LLM boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="local")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--no-response-format", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Execute the validated plan immediately")
    parser.add_argument("--input-json", default="{}", help="Root input JSON object for --execute")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.llm_graph_planner import plan_pipeline_with_llm
    from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
    from runtime.executor import execute_pipeline
    from runtime.models import Pipeline, PipelineNode
    from runtime.registry import CapabilityRegistry

    registry = CapabilityRegistry(root)
    registry.load()
    try:
        result = plan_pipeline_with_llm(
            args.goal,
            registry,
            config=LocalInferenceConfig(
                base_url=args.base_url.rstrip("/"),
                model=args.model,
                timeout_seconds=args.timeout,
                response_format=not args.no_response_format,
            ),
        )
    except LocalInferenceError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if args.execute:
        payload = json.loads(args.input_json)
        if not isinstance(payload, dict):
            print(json.dumps({"status": "failed", "error": "--input-json must decode to object"}, ensure_ascii=False, indent=2))
            return 2
        pipeline_data = result["pipeline"]
        pipeline = Pipeline(
            id=str(pipeline_data["id"]),
            version=str(pipeline_data["version"]),
            nodes=[
                PipelineNode(id=str(node["id"]), capability=str(node["capability"]), input=dict(node["input"]))
                for node in pipeline_data["nodes"]
            ],
            edges=[list(edge) for edge in pipeline_data["edges"]],
            retry_policy=dict(pipeline_data["retry_policy"]),
        )
        result["execution"] = execute_pipeline(root, pipeline, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
