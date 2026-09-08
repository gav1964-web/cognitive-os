"""Run the evidence-backed project development planning loop."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_development import run_project_development
from runtime.llm_gateway_bootstrap import ensure_llm_gateway_for_url
from runtime.local_inference import LocalInferenceConfig
from runtime.self_development_collector import collect_project_development_report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--goal", default="Find and prioritize the next evidence-backed project improvement")
    parser.add_argument("--chain-report", help="Optional full-chain report with case evidence for this project")
    parser.add_argument("--run-role-chain", action="store_true")
    parser.add_argument("--run-sandbox-experiment", action="store_true")
    parser.add_argument("--human-approval", help="Path to ProjectDevelopmentHumanApprovalDecision JSON")
    parser.add_argument("--architect-design", help="Path to ProjectDevelopmentImplementationDesign JSON")
    parser.add_argument(
        "--authorize-training-replay", action="store_true",
        help="Allow a training-only causal proposal in a sandbox; never applies source or promotes knowledge",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--use-l45-llm", action="store_true",
        help="Allow a bounded L4.5 hypothesis for an unknown failure mechanism",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    project_dir = _resolve(root, args.project_dir)
    prior = _prior_runs(root)
    chain_case = _chain_case(_resolve(root, args.chain_report), project_dir.name) if args.chain_report else None
    llm_config = LocalInferenceConfig.from_l45_env() if args.use_l45_llm else None
    gateway = (
        ensure_llm_gateway_for_url(root, llm_config.base_url)
        if llm_config is not None else {"status": "not_requested", "checked": False}
    )
    report = run_project_development(
        root=root,
        project_dir=project_dir,
        goal=args.goal,
        run_role_chain=args.run_role_chain,
        run_sandbox_experiment=args.run_sandbox_experiment,
        prior_runs=prior,
        chain_case=chain_case,
        human_approval=_read_json(_resolve(root, args.human_approval)) if args.human_approval else None,
        architect_design=_read_json(_resolve(root, args.architect_design)) if args.architect_design else None,
        authorize_training_replay=args.authorize_training_replay,
        llm_hypothesis_config=llm_config,
    )
    report["llm_gateway"] = gateway
    if args.write:
        written = _write(root, report)
        report["report_path"] = written.as_posix()
        report["prospective_collector"] = collect_project_development_report(
            root=root, report_path=written
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {
        "ready_for_experiment", "needs_replanning", "controlled_stop",
        "experiment_validated", "experiment_not_validated", "experiment_blocked",
        "research_required",
        "awaiting_human_approval", "implementation_candidate_ready", "implementation_design_ready",
        "implementation_designed",
    } else 1


def _prior_runs(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "artifacts" / "project_development").glob("project_development_*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def _chain_case(path: Path, project: str) -> dict[str, object] | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    case = next((dict(row) for row in payload.get("cases", []) if isinstance(row, dict) and row.get("project") == project), None)
    if case and isinstance(case.get("change_request"), dict):
        return {**case, **dict(case["change_request"])}
    return case


def _write(root: Path, report: dict[str, object]) -> Path:
    directory = root / "artifacts" / "project_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"project_development_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
