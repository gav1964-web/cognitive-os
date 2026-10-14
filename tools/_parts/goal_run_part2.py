from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from tools.l4_defaults import l4_base_url, l4_model, l4_response_format
except ModuleNotFoundError:  # Direct `python tools/goal_run.py` execution.
    from l4_defaults import l4_base_url, l4_model, l4_response_format
LOCAL_L4_FORBIDDEN_MODELS = {
    "local",
    "qwen-local",
    "qwen-local-cpu",
    "fast-local-cpu",
    "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
}
if __name__ == "__main__":
    raise SystemExit(main())

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

def _wants_project_development_proposal(goal: str) -> bool:
    lowered = goal.lower()
    markers = [
        "предложи развитие",
        "развитие проекта",
        "предложения по развитию",
        "предложения по улучшению",
        "улучшить проект",
        "улучшению проекта",
        "куда дальше",
        "следующие шаги",
        "development proposal",
        "improvement proposal",
        "next steps",
    ]
    return any(marker in lowered for marker in markers)

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
