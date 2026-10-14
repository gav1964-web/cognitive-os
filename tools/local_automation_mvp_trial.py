"""Run the registry-driven Local Automation MVP trial."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    parser = argparse.ArgumentParser(description="Run Local Automation MVP smoke trial.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--curriculum-dir", default="curricula/programmer_prompt_stage2")
    parser.add_argument("--case-registry", default="registry/local_automation_mvp_cases.json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    curriculum_dir = Path(args.curriculum_dir)
    if not curriculum_dir.is_absolute():
        curriculum_dir = root / curriculum_dir
    case_registry = Path(args.case_registry)
    if not case_registry.is_absolute():
        case_registry = root / case_registry

    report = run_trial(root=root, curriculum_dir=curriculum_dir, case_registry=case_registry, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_trial(*, root: Path, curriculum_dir: Path, case_registry: Path, write: bool = False) -> dict[str, Any]:
    cases_config = _load_cases(case_registry)
    rows = [_run_case(root=root, curriculum_dir=curriculum_dir, case=row, write=write) for row in cases_config["cases"]]
    failed = [row for row in rows if row["verdict"] != "passed"]
    return {
        "artifact_type": "LocalAutomationMVPTrialReport",
        "status": "ok" if not failed else "failed",
        "target": cases_config.get("target", "Prompt -> Verified Local Automation Package"),
        "case_registry": case_registry.as_posix(),
        "scope": {
            "in_scope": ["Python CLI", "local small service", "sandbox automation package", "fixture/mock verified workflows"],
            "out_of_scope": ["GUI", "SQL DB as required runtime state", "production deploy", "uncontrolled dependencies"],
        },
        "cases": rows,
        "summary": _summary(rows),
    }


def _load_cases(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "local_automation_mvp_cases.v1":
        raise ValueError("unsupported local automation MVP case registry schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("local automation MVP case registry requires non-empty cases list")
    return {"target": payload.get("target"), "cases": [dict(row) for row in cases]}


def _run_case(*, root: Path, curriculum_dir: Path, case: dict[str, Any], write: bool) -> dict[str, Any]:
    kind = str(case.get("kind") or "")
    handlers: dict[str, Callable[..., dict[str, Any]]] = {
        "stage2_verified_package": _run_stage2_case,
        "sandbox_operation_prompt": _run_sandbox_operation_case,
        "out_of_scope_prompt": _run_out_of_scope_case,
        "clarification_prompt": _run_clarification_case,
    }
    handler = handlers.get(kind)
    if handler is None:
        raise ValueError(f"unsupported local automation MVP case kind: {kind}")
    started = time.perf_counter()
    try:
        result = handler(root=root, curriculum_dir=curriculum_dir, prompt=str(case["prompt"]), write=write)
        ok, reason = _check_case(case=case, result=result)
    except Exception as exc:  # pragma: no cover - defensive reporting path.
        result = {"status": "exception", "error": str(exc)}
        ok, reason = False, str(exc)
    return {
        "case": str(case["id"]),
        "category": str(case.get("category") or "uncategorized"),
        "kind": kind,
        "expected": str(case.get("expected") or ""),
        "verdict": "passed" if ok else "failed",
        "reason": reason,
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "result_status": result.get("status"),
        "release_decision": dict(result.get("release_decision", {})).get("decision"),
        "project_dir": result.get("project_dir"),
    }


def _run_stage2_case(*, root: Path, curriculum_dir: Path, prompt: str, write: bool) -> dict[str, Any]:
    from runtime.verified_system_package import build_verified_system_package

    return build_verified_system_package(root=root, curriculum_dir=curriculum_dir, prompt=prompt, write=write)


def _run_sandbox_operation_case(*, root: Path, curriculum_dir: Path, prompt: str, write: bool) -> dict[str, Any]:
    del curriculum_dir
    from runtime.sandbox_prompt_field_trial import run_sandbox_prompt_field_trial

    return run_sandbox_prompt_field_trial(root=root, prompts=[prompt], use_model=True, write=write)


def _run_out_of_scope_case(*, root: Path, curriculum_dir: Path, prompt: str, write: bool) -> dict[str, Any]:
    from runtime.verified_system_package import build_verified_system_package

    return build_verified_system_package(
        root=root,
        curriculum_dir=curriculum_dir,
        prompt=prompt,
        write=write,
        allow_llm_sandbox_implementation=False,
    )


def _run_clarification_case(*, root: Path, curriculum_dir: Path, prompt: str, write: bool) -> dict[str, Any]:
    from runtime.verified_system_package import build_verified_system_package

    return build_verified_system_package(
        root=root,
        curriculum_dir=curriculum_dir,
        prompt=prompt,
        write=write,
        allow_llm_sandbox_implementation=False,
    )


def _check_case(*, case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    expected = str(case.get("expected") or "")
    if expected == "release_ready":
        decision = dict(result.get("release_decision", {})).get("decision")
        verification = dict(result.get("verification_report", {}))
        if result.get("status") == "ok" and decision in {"release_ready", "release_ready_with_risks"} and verification.get("status") == "passed":
            return True, "verified package passed project-scoped verification"
        return False, f"expected release-ready verified package, got status={result.get('status')} decision={decision}"
    if expected == "sandbox_verified":
        summary = dict(result.get("summary", {}))
        if result.get("status") == "ok" and summary.get("sandbox_verified") == 1 and summary.get("blocked") == 0:
            return True, "sandbox prompt produced a verified package"
        return False, f"expected one sandbox verified package, got {summary}"
    if expected == "blocked":
        if result.get("status") == "blocked":
            return True, "out-of-scope prompt was controlled-blocked"
        return False, f"expected controlled block, got status={result.get('status')}"
    if expected == "needs_clarification":
        gate = dict(result.get("prompt_adequacy", {}))
        boundary = dict(gate.get("boundary_classification", {}))
        questions = gate.get("clarification_questions") or []
        if (
            result.get("status") == "blocked"
            and gate.get("status") == "needs_clarification"
            and boundary.get("recommended_action") == "ask_clarification"
            and questions
        ):
            return True, "incomplete prompt produced clarification questions"
        return False, (
            "expected clarification block, got "
            f"status={result.get('status')} gate={gate.get('status')} "
            f"action={boundary.get('recommended_action')} questions={len(questions)}"
        )
    raise ValueError(f"unsupported local automation MVP expected result: {expected}")


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, dict[str, int]] = {}
    for row in rows:
        category = str(row["category"])
        bucket = categories.setdefault(category, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        bucket["passed" if row["verdict"] == "passed" else "failed"] += 1
    failed = sum(1 for row in rows if row["verdict"] != "passed")
    return {
        "case_count": len(rows),
        "passed": len(rows) - failed,
        "failed": failed,
        "pass_rate": round((len(rows) - failed) / len(rows), 3) if rows else 0.0,
        "categories": categories,
    }


if __name__ == "__main__":
    raise SystemExit(main())
