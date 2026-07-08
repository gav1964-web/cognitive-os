"""Run typed Cognitive OS role skills."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.project_benchmark import analyze_project
    from runtime.local_inference import LocalInferenceConfig
    from runtime.role_skills import (
        load_skill_registry,
        run_architect_skill,
        run_implementer_skill,
        run_reviewer_skill,
        run_spec_writer_skill,
        run_tester_skill,
        write_role_artifact,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--role", required=True, choices=["architect", "spec_writer", "implementer", "tester", "reviewer"])
    parser.add_argument("--goal")
    parser.add_argument("--project-dir")
    parser.add_argument("--report")
    parser.add_argument("--adr")
    parser.add_argument("--spec")
    parser.add_argument("--plan")
    parser.add_argument("--test-plan")
    parser.add_argument("--test-result")
    parser.add_argument("--constraint", action="append", default=[])
    parser.add_argument("--use-architect-llm", action="store_true")
    parser.add_argument("--architect-base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--architect-model", default="local")
    parser.add_argument("--architect-timeout", type=float, default=20.0)
    parser.add_argument("--architect-no-response-format", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    load_skill_registry(root)
    if args.role == "spec_writer":
        if not args.adr:
            raise SystemExit("--adr is required for --role spec_writer")
        artifact = run_spec_writer_skill(architecture_decision=_load_json(root, args.adr))
        if args.write:
            artifact["artifact_path"] = write_role_artifact(root, args.role, artifact).as_posix()
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if artifact["status"] == "ok" else 2
    if args.role == "implementer":
        if not args.spec:
            raise SystemExit("--spec is required for --role implementer")
        artifact = run_implementer_skill(technical_spec=_load_json(root, args.spec))
        if args.write:
            artifact["artifact_path"] = write_role_artifact(root, args.role, artifact).as_posix()
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if artifact["status"] == "ok" else 2
    if args.role == "tester":
        if not args.spec or not args.plan:
            raise SystemExit("--spec and --plan are required for --role tester")
        artifact = run_tester_skill(
            technical_spec=_load_json(root, args.spec),
            implementation_plan=_load_json(root, args.plan),
        )
        if args.write:
            artifact["artifact_path"] = write_role_artifact(root, args.role, artifact).as_posix()
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if artifact["status"] == "ok" else 2
    if args.role == "reviewer":
        if not args.spec or not args.plan or not args.test_plan:
            raise SystemExit("--spec, --plan and --test-plan are required for --role reviewer")
        test_result = _load_json(root, args.test_result) if args.test_result else None
        artifact = run_reviewer_skill(
            technical_spec=_load_json(root, args.spec),
            implementation_plan=_load_json(root, args.plan),
            test_plan=_load_json(root, args.test_plan),
            test_result=test_result,
        )
        if args.write:
            artifact["artifact_path"] = write_role_artifact(root, args.role, artifact).as_posix()
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if artifact["status"] == "ok" else 2

    if not args.goal:
        raise SystemExit("--goal is required for --role architect")
    report = _load_report(root, args.report)
    if report is None:
        if not args.project_dir:
            raise SystemExit("--project-dir or --report is required")
        project_dir = Path(args.project_dir)
        if not project_dir.is_absolute():
            project_dir = root / project_dir
        with _pushd(root):
            report = analyze_project(project_dir.resolve())["project_map_report"]

    advisory_config = None
    if args.use_architect_llm:
        advisory_config = LocalInferenceConfig(
            base_url=args.architect_base_url.rstrip("/"),
            model=args.architect_model,
            timeout_seconds=args.architect_timeout,
            response_format=not args.architect_no_response_format,
            provider_label="architect_advisory",
        )
    artifact = run_architect_skill(
        goal=args.goal,
        project_report=report,
        constraints=args.constraint,
        advisory_config=advisory_config,
    )
    if args.write:
        artifact["artifact_path"] = write_role_artifact(root, args.role, artifact).as_posix()
    print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if artifact["status"] == "ok" else 2


def _load_report(root: Path, report_arg: str | None) -> dict[str, object] | None:
    if not report_arg:
        return None
    return _load_json(root, report_arg)


def _load_json(root: Path, path_arg: str) -> dict[str, object]:
    path = Path(path_arg)
    if not path.is_absolute():
        path = root / path
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    raise SystemExit(main())
