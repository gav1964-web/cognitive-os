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
    from runtime.role_directory import RoleDirectoryError, pipeline_step_for_role, role_entry
    from runtime.role_skills import load_skill_registry, run_role_skill, write_role_artifact

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--role", required=True)
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
    try:
        role_entry(args.role)
    except RoleDirectoryError as exc:
        print(
            json.dumps(
                {
                    "artifact_type": "RoleSkillRun",
                    "status": "blocked",
                    "role": args.role,
                    "reason": str(exc),
                    "policy": "roles are loaded only from config/role_directory.json",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    try:
        step = pipeline_step_for_role(args.role)
    except RoleDirectoryError as exc:
        print(
            json.dumps(
                {
                    "artifact_type": "RoleSkillRun",
                    "status": "blocked",
                    "role": args.role,
                    "reason": str(exc),
                    "policy": "runnable role bindings are loaded only from config/role_directory.json",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    advisory_config = None
    if args.use_architect_llm:
        advisory_config = LocalInferenceConfig(
            base_url=args.architect_base_url.rstrip("/"),
            model=args.architect_model,
            timeout_seconds=args.architect_timeout,
            response_format=not args.architect_no_response_format,
            provider_label="architect_advisory",
        )
    context = _cli_context(root, args, step=step, advisory_config=advisory_config)
    kwargs = {
        str(name): _resolve_binding(value, context)
        for name, value in dict(step.get("bindings", {})).items()
    }
    optional_inputs = {"advisory_config", "test_result", "executable_acceptance_result"}
    missing = [name for name, value in kwargs.items() if value is None and name not in optional_inputs]
    if missing:
        raise SystemExit(f"missing inputs for role {args.role}: {', '.join(missing)}")
    artifact = run_role_skill(args.role, **kwargs)
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
    if not path.exists():
        raise SystemExit(f"input artifact not found: {path.as_posix()}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input artifact is not valid JSON: {path.as_posix()}: {exc}") from exc


def _cli_context(root: Path, args: argparse.Namespace, *, step: dict[str, object], advisory_config: object) -> dict[str, object]:
    artifacts = _load_cli_artifacts(root, args)
    context: dict[str, object] = {
        "goal": args.goal,
        "project_report": None,
        "advisory_config": advisory_config,
        "test_result": _load_json(root, args.test_result) if args.test_result else None,
        "artifacts": artifacts,
        "constraints": args.constraint,
    }
    if _bindings_reference(step, "$project_report"):
        context["project_report"] = _load_or_analyze_report(root, args)
    return context


def _load_cli_artifacts(root: Path, args: argparse.Namespace) -> dict[str, dict[str, object]]:
    aliases = {
        "architecture_decision": args.adr,
        "technical_spec": args.spec,
        "implementation_plan": args.plan,
        "test_plan": args.test_plan,
    }
    return {
        key: _load_json(root, path)
        for key, path in aliases.items()
        if path
    }


def _load_or_analyze_report(root: Path, args: argparse.Namespace) -> dict[str, object]:
    if not args.goal:
        raise SystemExit("--goal is required when the configured role consumes project_report")
    report = _load_report(root, args.report)
    if report is not None:
        return report
    if not args.project_dir:
        raise SystemExit("--project-dir or --report is required when the configured role consumes project_report")
    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = root / project_dir
    from runtime.project_benchmark import analyze_project

    with _pushd(root):
        return analyze_project(project_dir.resolve())["project_map_report"]


def _bindings_reference(step: dict[str, object], target: str) -> bool:
    return target in [str(value) for value in dict(step.get("bindings", {})).values()]


def _resolve_binding(value: object, context: dict[str, object]) -> object:
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    current: object = context
    for part in value[1:].split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


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
