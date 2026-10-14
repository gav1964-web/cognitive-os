"""Build a Stage 2 Verified System Package from a bounded prompt."""

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

    from runtime.verified_system_package import build_verified_system_package
    from runtime.greenfield_role_pipeline import run_greenfield_role_pipeline

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--curriculum-dir", default="curricula/programmer_prompt_stage2")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--use-l45-llm", action="store_true")
    parser.add_argument("--no-llm-sandbox-implementation", action="store_true")
    parser.add_argument("--planning-only", action="store_true", help="Run greenfield Architect/SpecWriter planning without implementation.")
    parser.add_argument(
        "--question-mode",
        choices=["continue", "continue_with_assumptions", "ask", "ask_user", "ask_user_before_spec"],
        default="continue_with_assumptions",
        help="How Architect handles open questions in --planning-only mode.",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.planning_only:
        report = run_greenfield_role_pipeline(
            root=root,
            prompt=args.prompt,
            write=args.write,
            question_mode=args.question_mode,
            use_l45_model=args.use_l45_llm,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["status"] in {"ok", "needs_clarification", "needs_improvement"} else 1

    curriculum_dir = Path(args.curriculum_dir)
    if not curriculum_dir.is_absolute():
        curriculum_dir = root / curriculum_dir
    report = build_verified_system_package(
        root=root,
        prompt=args.prompt,
        curriculum_dir=curriculum_dir,
        write=args.write,
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        use_l45_model=args.use_l45_llm,
        allow_llm_sandbox_implementation=not args.no_llm_sandbox_implementation,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
