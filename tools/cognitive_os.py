"""Unified Cognitive OS command line entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.cognitive_os_entry import run_cognitive_os

    parser = argparse.ArgumentParser(description="Run Cognitive OS through a single configured entry route.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--mode", default="auto", choices=["auto", "planning", "architecture", "spec", "prompt_to_product", "project_foundation_analysis"])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--use-l45-llm", action="store_true")
    parser.add_argument(
        "--question-mode",
        choices=["continue", "continue_with_assumptions", "ask", "ask_user", "ask_user_before_spec"],
        default="continue_with_assumptions",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir).resolve() if args.project_dir else None
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    report = run_cognitive_os(
        root=root,
        prompt=args.prompt,
        project_dir=project_dir,
        output_dir=output_dir,
        mode=args.mode,
        write=args.write,
        use_l45_model=args.use_l45_llm,
        question_mode=args.question_mode,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
