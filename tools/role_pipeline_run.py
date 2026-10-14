"""Run the role pipeline with configured upstream LLM advisories by default."""

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
    from dataclasses import replace
    from runtime.role_inference import role_model_config

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument('--task-contract', help='Workspace-relative explicit task requirements; planning only')
    parser.add_argument('--research-request', action='append', default=[],
                        help='JSON with role, plugin owner, question, allowed domains and version scope')
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-executor", action="store_true")
    parser.add_argument("--run-transform", action="store_true")
    parser.add_argument("--force-transform", action="store_true")
    parser.add_argument("--use-architect-llm", action="store_true")
    parser.add_argument("--no-role-llm", action="store_true",
                        help="Retain legacy Analyzer behavior; disable configured role advisories")
    parser.add_argument("--architect-base-url")
    parser.add_argument("--architect-model")
    parser.add_argument("--architect-timeout", type=float)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = root / project_dir
    advisory_config = None
    if args.use_architect_llm or any((args.architect_base_url, args.architect_model, args.architect_timeout)):
        base = role_model_config('architect')
        advisory_config = replace(base,
            base_url=(args.architect_base_url or base.base_url).rstrip('/'),
            model=args.architect_model or base.model,
            timeout_seconds=args.architect_timeout or base.timeout_seconds)
    from runtime.llm_gateway_bootstrap import ensure_llm_gateway_for_url
    configs = [role_model_config(role) for role in ('analyzer', 'architect', 'spec_writer')] if not args.no_role_llm else []
    if advisory_config:
        configs.append(advisory_config)
    for url in sorted({cfg.base_url for cfg in configs}):
        if ensure_llm_gateway_for_url(root, url)['status'] == 'failed':
            parser.error('managed gateway readiness failed before role inference')
    result = run_role_pipeline(
        root=root,
        project_dir=project_dir.resolve(),
        goal=args.goal,
        write=args.write,
        run_executor=args.run_executor,
        run_transform=args.run_transform,
        force_transform=args.force_transform,
        architect_advisory_config=advisory_config,
        use_role_llm=not args.no_role_llm,
        research_requests=[_read_task_contract(root, name) for name in args.research_request],
        task_contract=_read_task_contract(root, args.task_contract) if args.task_contract else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


def _read_task_contract(root, name):
    from runtime.stage_finalization_workspace import owned_path
    path = owned_path(root, name)
    if path.name == 'config.json' or path.name.startswith('.env') or path.stat().st_size > 100_000:
        raise ValueError('unsupported_task_contract_file')
    return json.loads(path.read_text(encoding='utf-8'))


if __name__ == "__main__":
    raise SystemExit(main())
