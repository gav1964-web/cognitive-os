"""Run greenfield Architect -> SpecWriter pipeline from a user prompt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.greenfield_role_pipeline import run_greenfield_role_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-dir", help="Deliver a supported new project into an empty directory under artifacts; requires --write.")
    parser.add_argument(
        "--question-mode",
        choices=["continue", "continue_with_assumptions", "ask", "ask_user", "ask_user_before_spec"],
        default="continue_with_assumptions",
        help="How ArchitectSkill handles open questions before SpecWriter handoff.",
    )
    parser.add_argument("--use-l45-llm", action="store_true", help="Allow L4.5 model-backed semantic fallback.")
    parser.add_argument(
        "--allow-generic-pattern",
        action="store_true",
        help="Allow generic_product to continue to SpecWriter. Default is to emit a semantic gap.",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.output_dir:
        if not args.write or args.use_l45_llm or args.allow_generic_pattern or args.question_mode != 'continue_with_assumptions':
            parser.error('delivery requires --write and default bounded planning options')
        from runtime.role_pipeline import run_role_pipeline
        from runtime.evaluation_route_execution import verify_task15
        from uuid import uuid4
        output = Path(args.output_dir)
        output = output if output.is_absolute() else root / output
        checks = root / 'artifacts/verification' / ('greenfield-' + uuid4().hex[:12])
        report = run_role_pipeline(root=root, project_dir=output, goal=args.prompt,
            mode='greenfield', write=True, run_executor=True,
            delivery_verifier=lambda project: verify_task15(project, checks))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['status'] == 'completed' else 1
    report = run_greenfield_role_pipeline(
        root=root,
        prompt=args.prompt,
        write=args.write,
        question_mode=args.question_mode,
        use_l45_model=args.use_l45_llm,
        require_specific_pattern=not args.allow_generic_pattern,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "needs_clarification", "needs_improvement"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
