"""Run the full deterministic role pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.role_pipeline import run_role_pipeline
    from runtime.local_inference import LocalInferenceConfig

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-executor", action="store_true")
    parser.add_argument("--run-transform", action="store_true")
    parser.add_argument("--force-transform", action="store_true")
    parser.add_argument("--use-architect-llm", action="store_true")
    parser.add_argument("--architect-base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--architect-model", default="local")
    parser.add_argument("--architect-timeout", type=float, default=20.0)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = root / project_dir
    advisory_config = None
    if args.use_architect_llm:
        advisory_config = LocalInferenceConfig(
            base_url=args.architect_base_url.rstrip("/"),
            model=args.architect_model,
            timeout_seconds=args.architect_timeout,
            provider_label="architect_advisory",
        )
    result = run_role_pipeline(
        root=root,
        project_dir=project_dir.resolve(),
        goal=args.goal,
        write=args.write,
        run_executor=args.run_executor,
        run_transform=args.run_transform,
        force_transform=args.force_transform,
        architect_advisory_config=advisory_config,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
