"""Run local negative project fixtures through the role foundation pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_foundation_pipeline import run_role_foundation_pipeline


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()
    benchmarks_dir = (root / args.benchmarks_dir).resolve()
    expectations = _load_json(benchmarks_dir / "expectations.json")
    cases = []
    for case in expectations.get("cases", []):
        cases.append(_run_case(root=root, benchmarks_dir=benchmarks_dir, expectation=dict(case), write=args.write))
    report = _report(cases)
    if args.write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"nasty_project_redteam_{_stamp()}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--benchmarks-dir",
        default="benchmarks/nasty_local_projects",
        help="Directory with projects/ and expectations.json.",
    )
    parser.add_argument("--write", action="store_true", help="Write role artifacts and the red-team report.")
    return parser.parse_args()


def _run_case(*, root: Path, benchmarks_dir: Path, expectation: dict[str, Any], write: bool) -> dict[str, Any]:
    project_name = str(expectation["project"])
    project_dir = benchmarks_dir / "projects" / project_name
    result = run_role_foundation_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"Red-team local project analysis for {project_name}",
        write=write,
    )
    artifacts = _load_artifacts(result)
    observed = _observed(result, artifacts)
    checks = _checks(expectation, observed)
    return {
        "project": project_name,
        "status": "ok" if all(check["passed"] for check in checks) else "failed",
        "checks": checks,
        "observed": observed,
        "report_path": result.get("report_path"),
    }


def _load_artifacts(result: dict[str, Any]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for name, summary in dict(result.get("artifacts", {})).items():
        path = dict(summary).get("path")
        if path:
            loaded[name] = _load_json(Path(path))
    return loaded


def _observed(result: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    project_map = dict(artifacts.get("project_map_report", {})).get("content", {})
    adr = artifacts.get("architecture_decision", {})
    spec = artifacts.get("technical_spec", {})
    profile = dict(dict(adr).get("architecture_synthesis", {})).get("project_profile", {})
    source_health = dict(project_map).get("source_tree_health") or dict(project_map).get("source_health") or {}
    security = dict(project_map).get("security_posture") or dict(project_map).get("security_health") or {}
    risks = [
        str(row.get("code") or row.get("id"))
        for row in dict(project_map).get("risks", [])
        if isinstance(row, dict) and (row.get("code") or row.get("id"))
    ]
    ranked = list(dict(dict(spec).get("extraction_contract", {})).get("ranked_candidates", []) or [])
    return {
        "pipeline_status": result.get("status"),
        "architect_red_team_status": dict(result.get("architect_red_team", {})).get("status"),
        "archetype": dict(profile).get("archetype"),
        "selected_candidate": result.get("selected_extraction_candidate"),
        "source_shape": dict(source_health).get("project_shape") or dict(source_health).get("shape"),
        "source_status": dict(source_health).get("status"),
        "security_status": dict(security).get("status"),
        "risks": sorted(set(risks)),
        "ranked_reasons": {
            str(row.get("source")): list(row.get("reasons", []) or [])
            for row in ranked
            if isinstance(row, dict) and row.get("source")
        },
    }


def _checks(expectation: dict[str, Any], observed: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    _add_check(checks, "status", observed.get("pipeline_status") == expectation.get("expected_status"), observed.get("pipeline_status"))
    if expectation.get("expected_archetype"):
        _add_check(checks, "archetype", observed.get("archetype") == expectation.get("expected_archetype"), observed.get("archetype"))
    for archetype in expectation.get("forbidden_archetypes", []) or []:
        _add_check(checks, f"forbidden_archetype:{archetype}", observed.get("archetype") != archetype, observed.get("archetype"))
    if expectation.get("expected_candidate"):
        _add_check(
            checks,
            "selected_candidate",
            observed.get("selected_candidate") == expectation.get("expected_candidate"),
            observed.get("selected_candidate"),
        )
    if expectation.get("expected_source_shape"):
        _add_check(checks, "source_shape", observed.get("source_shape") == expectation.get("expected_source_shape"), observed.get("source_shape"))
    if expectation.get("expected_source_status"):
        _add_check(checks, "source_status", observed.get("source_status") == expectation.get("expected_source_status"), observed.get("source_status"))
    if expectation.get("expected_security_status"):
        _add_check(
            checks,
            "security_status",
            observed.get("security_status") == expectation.get("expected_security_status"),
            observed.get("security_status"),
        )
    risks = set(observed.get("risks", []) or [])
    for risk in expectation.get("required_risks", []) or []:
        _add_check(checks, f"risk:{risk}", risk in risks, sorted(risks))
    reason_text = "\n".join(
        reason
        for reasons in dict(observed.get("ranked_reasons", {})).values()
        for reason in reasons
    )
    for fragment in expectation.get("required_spec_reason_fragments", []) or []:
        _add_check(checks, f"spec_reason:{fragment}", fragment.lower() in reason_text.lower(), fragment)
    return checks


def _add_check(checks: list[dict[str, Any]], name: str, passed: bool, observed: Any) -> None:
    checks.append({"name": name, "passed": bool(passed), "observed": observed})


def _report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed_cases = sum(1 for case in cases if case["status"] == "ok")
    return {
        "kind": "nasty_project_redteam",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed_cases == len(cases),
        "passed_cases": passed_cases,
        "total_cases": len(cases),
        "cases": cases,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
