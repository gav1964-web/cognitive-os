"""Run Project Analyzer and all role questionnaires over GitHub projects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_benchmark import _deterministic_signal_config, analyze_project
from runtime.project_interpreter import interpret_project_report
from runtime.role_pipeline import run_role_pipeline
from runtime.role_questionnaire import build_role_questionnaire_report
from runtime.target_quality import target_quality_report


DEFAULT_REPOS = [
    "psf/requests",
    "encode/httpx",
    "scrapy/scrapy",
    "pallets/flask",
    "django/django",
    "encode/starlette",
    "fastapi/fastapi",
    "celery/celery",
    "rq/rq",
    "pytest-dev/pytest",
    "tox-dev/tox",
    "PyCQA/flake8",
    "psf/black",
    "python-poetry/poetry",
    "pypa/pip",
    "pypa/setuptools",
    "sqlalchemy/sqlalchemy",
    "msiemens/tinydb",
    "matplotlib/matplotlib",
    "numpy/numpy",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--work-dir", default="artifacts/github_role_questionnaire_20c")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--clone", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    work_dir = Path(args.work_dir)
    if not work_dir.is_absolute():
        work_dir = root / work_dir
    repos = args.repo or DEFAULT_REPOS
    if args.limit > 0:
        repos = repos[: args.limit]

    report = run_probe(root=root, work_dir=work_dir, repos=repos, clone=args.clone)
    if args.write:
        report.update(write_report(work_dir, report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "needs_review"} else 1


def run_probe(*, root: Path, work_dir: Path, repos: list[str], clone: bool = False) -> dict[str, Any]:
    src_dir = work_dir / "src"
    cases_dir = work_dir / "cases"
    src_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    for repo in repos:
        project_dir = _ensure_repo(src_dir, repo, clone=clone)
        cases.append(_run_case(root=root, cases_dir=cases_dir, repo=repo, project_dir=project_dir))

    summary = _summary(cases)
    return {
        "status": "ok" if summary["failed"] == 0 else "needs_review",
        "artifact_type": "GitHubRoleQuestionnaireProbe",
        "milestone": "GitHub Role Questionnaire 20 v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": summary,
        "invariants": {
            "llm_invoked": sum(1 for case in cases if case["llm_invoked"]),
            "source_projects_modified": sum(1 for case in cases if case["source_code_changes"]),
            "questionnaire_answers_are_evidence_bound": True,
            "role_artifacts_are_api_between_layers": True,
            "teacher_reference_is_ground_truth": False,
            "automatic_code_changes_from_own_output": False,
        },
        "cases": cases,
    }


def write_report(work_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    out_dir = work_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = out_dir / f"github_role_questionnaire_{stamp}.json"
    md_path = out_dir / f"github_role_questionnaire_{stamp}.md"
    paths = {"report_path": json_path.as_posix(), "markdown_path": md_path.as_posix()}
    payload = {**report, **paths}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return paths


def _ensure_repo(src_dir: Path, repo: str, *, clone: bool) -> Path:
    name = repo.replace("/", "__")
    target = src_dir / name
    if target.exists():
        return target
    if not clone:
        raise FileNotFoundError(f"repository is missing and --clone is false: {target}")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            f"https://github.com/{repo}.git",
            str(target),
        ],
        check=True,
        timeout=900,
    )
    return target


def _run_case(*, root: Path, cases_dir: Path, repo: str, project_dir: Path) -> dict[str, Any]:
    case_id = repo.replace("/", "__")
    case_dir = cases_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    try:
        outputs = analyze_project(project_dir)
        goal_report = {
            "goal_id": f"github_role_questionnaire_{case_id}",
            "goal": f"Analyze {repo} through all Cognitive OS roles.",
            "execution": {"status": "ok", "completed_nodes": list(outputs), "outputs": outputs},
        }
        interpretation = interpret_project_report(goal_report, signal_config=_deterministic_signal_config())
        questionnaire = build_role_questionnaire_report(project=repo, goal_report=goal_report, interpretation=interpretation)
        role_pipeline = run_role_pipeline(
            root=root,
            project_dir=project_dir,
            goal=f"Assess and prepare first safe transformation for {repo}",
            write=False,
        )
        case_payload = {
            "repo": repo,
            "project_dir": project_dir.as_posix(),
            "status": "ok",
            "summary": _case_summary(outputs, interpretation, questionnaire, role_pipeline),
            "questionnaire": questionnaire,
            "role_pipeline": _role_pipeline_excerpt(role_pipeline),
        }
        (case_dir / "case.json").write_text(
            json.dumps(case_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "repo": repo,
            "status": "ok",
            "case_path": (case_dir / "case.json").as_posix(),
            **case_payload["summary"],
        }
    except Exception as exc:  # pragma: no cover - exercised by field trials, reported not hidden.
        error_payload = {"repo": repo, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        (case_dir / "error.json").write_text(
            json.dumps(error_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "repo": repo,
            "status": "failed",
            "case_path": (case_dir / "error.json").as_posix(),
            "error": error_payload["error"],
            "llm_invoked": False,
            "source_code_changes": _git_dirty(project_dir),
            "question_count": 0,
            "gap_count": 0,
            "role_pipeline_recommendation": "failed",
            "role_pipeline_next_action": "failed",
        }


def _case_summary(
    outputs: dict[str, Any],
    interpretation: dict[str, Any],
    questionnaire: dict[str, Any],
    role_pipeline: dict[str, Any],
) -> dict[str, Any]:
    report = dict(outputs.get("project_map_report", {}))
    summary = dict(report.get("summary", {}))
    role_summary = dict(questionnaire.get("summary", {}))
    architecture = dict(interpretation.get("architecture_synthesis", {}))
    return {
        "entrypoints": len(summary.get("entrypoints", [])),
        "frameworks": summary.get("frameworks", []),
        "languages": summary.get("languages", []),
        "risks": len(report.get("risks", [])),
        "matched_rule": _rule_id(architecture),
        "question_count": questionnaire.get("question_count", 0),
        "role_count": role_summary.get("role_count", 0),
        "gap_count": role_summary.get("gap_count", 0),
        "roles_without_full_question_set": role_summary.get("roles_without_full_question_set", []),
        "role_pipeline_recommendation": role_pipeline.get("recommendation"),
        "role_pipeline_next_action": role_pipeline.get("next_action"),
        "role_quality": role_pipeline.get("role_quality", {}),
        "target_quality": target_quality_report(dict(role_pipeline.get("role_quality", {}))),
        "llm_invoked": bool(
            dict(role_pipeline.get("safety", {})).get("llm_invoked")
            or dict(questionnaire.get("policy", {})).get("llm_invoked")
        ),
        "source_code_changes": _git_dirty(Path(str(role_pipeline.get("project", ".")))),
    }


def _role_pipeline_excerpt(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "recommendation": payload.get("recommendation"),
        "next_action": payload.get("next_action"),
        "role_quality": payload.get("role_quality"),
        "safety": payload.get("safety"),
        "artifacts": payload.get("artifacts"),
    }


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(cases)
    ok = sum(1 for case in cases if case["status"] == "ok")
    failed = count - ok
    question_count = sum(int(case.get("question_count") or 0) for case in cases)
    gap_count = sum(int(case.get("gap_count") or 0) for case in cases)
    recommendations = _counts(str(case.get("role_pipeline_recommendation")) for case in cases)
    actions = _counts(str(case.get("role_pipeline_next_action")) for case in cases)
    rules = _counts(str(case.get("matched_rule")) for case in cases if case.get("matched_rule"))
    target_quality = _counts(str(dict(case.get("target_quality") or {}).get("status")) for case in cases)
    return {
        "ok": ok,
        "failed": failed,
        "question_count": question_count,
        "avg_questions_per_project": round(question_count / count, 2) if count else 0.0,
        "gap_count": gap_count,
        "avg_gaps_per_project": round(gap_count / count, 2) if count else 0.0,
        "llm_invoked": sum(1 for case in cases if case.get("llm_invoked")),
        "source_code_changes": sum(1 for case in cases if case.get("source_code_changes")),
        "role_pipeline_recommendations": recommendations,
        "role_pipeline_next_actions": actions,
        "matched_rules": rules,
        "target_quality": target_quality,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['milestone']}",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Projects: `{report['project_count']}`",
        f"Status: `{report['status']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Cases", ""])
    for case in report["cases"]:
        lines.append(
            f"- `{case['repo']}`: `{case['status']}`, questions `{case.get('question_count', 0)}`, "
            f"gaps `{case.get('gap_count', 0)}`, action `{case.get('role_pipeline_next_action')}`, "
            f"target `{dict(case.get('target_quality') or {}).get('status')}`"
        )
    lines.append("")
    return "\n".join(lines)


def _rule_id(value: Any) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("knowledge"), dict):
            nested = value["knowledge"].get("matched_rule")
            if nested:
                return str(nested)
        return str(value.get("rule_id") or value.get("id") or "")
    return str(value or "")


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if value:
            result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _git_dirty(project_dir: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return bool(result.stdout.strip())


if __name__ == "__main__":
    raise SystemExit(main())
