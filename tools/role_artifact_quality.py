"""Run deterministic quality checks for L4 role artifact wording."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_artifact_quality import evaluate_role_artifacts
from runtime.role_artifact_interpreter import run_role_artifact_pipeline
from runtime.project_benchmark import analyze_project
from runtime.role_skill_common import load_skill_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--benchmarks-dir", default="benchmarks/project_analyzer/projects")
    parser.add_argument("--project", default=None)
    parser.add_argument("--project-dir", action="append", default=[])
    parser.add_argument("--min-score", type=float, default=0.9)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    projects = _explicit_projects(root, args.project_dir) if args.project_dir else _projects(root / args.benchmarks_dir, args.project)
    cases = [_run_case(root, project) for project in projects]
    avg_score = _ratio(sum(case["quality"]["score"] for case in cases), len(cases))
    warnings = sum(len(case["quality"]["warnings"]) for case in cases)
    passed = sum(1 for case in cases if case["quality"]["passed"])
    payload = {
        "status": "ok" if cases and passed == len(cases) and avg_score >= args.min_score and warnings == 0 else "failed",
        "kind": "role_artifact_quality",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": {"avg_score": avg_score, "passed": passed, "warnings": warnings, "min_score": args.min_score},
        "cases": cases,
    }
    if args.write:
        payload["report_path"] = _write_report(root, payload).as_posix()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


def _run_case(root: Path, project_dir: Path) -> dict[str, object]:
    load_skill_registry(root)
    with _pushd(root):
        project_report = analyze_project(project_dir)["project_map_report"]
    goal = f"Produce clear ADR and TechnicalSpec for first safe transformation in {project_dir.name}"
    artifacts = run_role_artifact_pipeline(goal=goal, project_report=project_report)
    quality = evaluate_role_artifacts(artifacts)
    return {"project": project_dir.name, "status": "ok" if quality["passed"] else "failed", "quality": quality}


def _projects(projects_dir: Path, selected: str | None) -> list[Path]:
    if selected:
        path = projects_dir / selected
        if not path.is_dir():
            raise FileNotFoundError(f"benchmark project not found: {path}")
        return [path]
    return sorted(path for path in projects_dir.iterdir() if path.is_dir())


def _explicit_projects(root: Path, values: list[str]) -> list[Path]:
    projects = []
    for value in values:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if not path.is_dir():
            raise FileNotFoundError(f"project directory not found: {path}")
        projects.append(path.resolve())
    return projects


def _write_report(root: Path, payload: dict[str, object]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_artifact_quality_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)


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
