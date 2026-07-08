"""Run Cognitive OS MVP smoke scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.executor import execute_pipeline
from runtime.pipeline import load_pipeline
from runtime.registry import CapabilityRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["happy", "quarantine", "no_fallback"], default="happy")
    parser.add_argument("--reset-registry", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    pipeline = load_pipeline(root / "pipelines" / "fetch_parse_save.json")
    if args.scenario == "happy":
        root_input = {"url": "mock://ok", "output_path": "artifacts/outputs/happy.json"}
    elif args.scenario == "quarantine":
        root_input = {"url": "mock://broken_dependency", "output_path": "artifacts/outputs/quarantine.json"}
    else:
        registry = CapabilityRegistry(root)
        registry.reset_from_plugins()
        registry.mark_status("parse_title_fallback", "retired")
        root_input = {"url": "mock://broken_dependency", "output_path": "artifacts/outputs/no_fallback.json"}
        args.reset_registry = False
    result = execute_pipeline(root, pipeline, root_input, reset_registry=args.reset_registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "stopped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
