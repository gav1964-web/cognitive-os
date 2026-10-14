"""Run active exception-pickle KB application on holdout candidates."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_active_application import (
    run_exception_pickle_active_application_trial,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--audit",
        default="artifacts/project_development/exception_pickle_candidate_audit_20260831T120556188729Z.json",
    )
    parser.add_argument(
        "--transfer-ledger",
        default="artifacts/project_development/supervised_exception_pickle_transfer_ledger.json",
    )
    parser.add_argument(
        "--application-ledger",
        default="artifacts/project_development/exception_pickle_active_application_ledger.json",
    )
    parser.add_argument("--object-contract-admission")
    parser.add_argument("--maximum-attempts", type=int, default=8)
    parser.add_argument("--maximum-accepted-applications", type=int, default=1)
    parser.add_argument("--maximum-replay-blockers", type=int)
    parser.add_argument("--maximum-static-patch-blockers-per-project", type=int, default=1)
    parser.add_argument("--maximum-replay-blockers-per-project", type=int, default=1)
    parser.add_argument("--no-prioritize-patchable-candidates", action="store_true")
    parser.add_argument("--no-prioritize-dependency-light-candidates", action="store_true")
    parser.add_argument("--no-target-import-stubs", action="store_true")
    parser.add_argument("--only-readmission-frontier", action="store_true")
    parser.add_argument("--only-import-isolation-frontier", action="store_true")
    parser.add_argument("--readmission-subtype")
    parser.add_argument("--import-isolation-missing-kind")
    parser.add_argument("--import-isolation-batch-profile")
    parser.add_argument("--import-isolation-cluster")
    parser.add_argument(
        "--candidate-key",
        action="append",
        default=[],
        help="Exact project::path:Class.__init__ key to reprobe.",
    )
    parser.add_argument(
        "--allow-candidate-key-write",
        action="store_true",
        help="Allow --candidate-key together with --write for audited exact-target promotion.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.candidate_key and args.write and not args.allow_candidate_key_write:
        parser.error("--candidate-key with --write requires --allow-candidate-key-write")
    root = Path(args.root).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = run_exception_pickle_active_application_trial(
        root=root,
        execution_dir=root / "artifacts" / "project_development" / "active_application" / stamp,
        audit_path=Path(args.audit),
        transfer_ledger_path=Path(args.transfer_ledger),
        application_ledger_path=Path(args.application_ledger),
        object_contract_admission_path=Path(args.object_contract_admission)
        if args.object_contract_admission
        else None,
        maximum_attempts=args.maximum_attempts,
        maximum_accepted_applications=args.maximum_accepted_applications,
        maximum_replay_blockers=args.maximum_replay_blockers,
        maximum_static_patch_blockers_per_project=args.maximum_static_patch_blockers_per_project,
        maximum_replay_blockers_per_project=args.maximum_replay_blockers_per_project,
        prioritize_patchable_candidates=not args.no_prioritize_patchable_candidates,
        prioritize_dependency_light_candidates=not args.no_prioritize_dependency_light_candidates,
        allow_target_import_stubs=not args.no_target_import_stubs,
        only_readmission_frontier=args.only_readmission_frontier,
        only_import_isolation_frontier=args.only_import_isolation_frontier,
        readmission_subtype=args.readmission_subtype,
        import_isolation_missing_kind=args.import_isolation_missing_kind,
        import_isolation_batch_profile=args.import_isolation_batch_profile,
        import_isolation_cluster=args.import_isolation_cluster,
        candidate_keys=list(args.candidate_key or []),
        update_application_ledger=args.write,
    )
    if args.write or args.write_report:
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"exception_pickle_active_application_{stamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = path.as_posix()
    output = _summary(report) if args.summary_only else report
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "applied_active_kb" else 2


def _summary(report: dict) -> dict:
    selected = dict(report.get("selected_application") or {})
    return {
        "status": report.get("status"),
        "attempt_count": report.get("attempt_count"),
        "selected_application_count": report.get("selected_application_count"),
        "stop_reason": report.get("stop_reason"),
        "skipped_candidate_count": report.get("skipped_candidate_count"),
        "maximum_accepted_applications": report.get("maximum_accepted_applications"),
        "maximum_replay_blockers": report.get("maximum_replay_blockers"),
        "maximum_static_patch_blockers_per_project": report.get(
            "maximum_static_patch_blockers_per_project"
        ),
        "maximum_replay_blockers_per_project": report.get("maximum_replay_blockers_per_project"),
        "prioritize_patchable_candidates": report.get("prioritize_patchable_candidates"),
        "prioritize_dependency_light_candidates": report.get(
            "prioritize_dependency_light_candidates"
        ),
        "allow_target_import_stubs": report.get("allow_target_import_stubs"),
        "only_readmission_frontier": report.get("only_readmission_frontier"),
        "only_import_isolation_frontier": report.get("only_import_isolation_frontier"),
        "readmission_subtype": report.get("readmission_subtype"),
        "import_isolation_missing_kind": report.get("import_isolation_missing_kind"),
        "import_isolation_batch_profile": report.get("import_isolation_batch_profile"),
        "import_isolation_cluster": report.get("import_isolation_cluster"),
        "candidate_keys": report.get("candidate_keys") or [],
        "import_isolation_batch_summary": report.get("import_isolation_batch_summary") or {},
        "update_application_ledger": report.get("update_application_ledger"),
        "replay_blocker_limit_reached": report.get("replay_blocker_limit_reached"),
        "blocker_summary": report.get("blocker_summary") or {},
        "selected_application": selected.get("candidate") if selected else None,
        "selected_applications": [
            dict(item.get("candidate") or {})
            for item in report.get("selected_applications") or []
            if isinstance(item, dict)
        ],
        "report_path": report.get("report_path"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
