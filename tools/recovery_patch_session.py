from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or execute an admitted recovery patch session")
    parser.add_argument("--root", default=".")
    parser.add_argument("--project", required=True)
    parser.add_argument("--field-trial-report", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approver")
    parser.add_argument("--approve-digest")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    trial = _read_json(Path(args.field_trial_report))
    package = _read_json(Path(str(trial.get("package_path") or "")))
    admission = _read_json(Path(str(trial.get("admission_path") or "")))
    approval = None
    if args.apply:
        approval = {
            "approved": True,
            "decision": "approve_apply",
            "approver": args.approver,
            "patch_digest": args.approve_digest,
        }
    from runtime.recovery_patch_session import run_recovery_patch_session

    report = run_recovery_patch_session(
        root=root,
        project_dir=(root / args.project).resolve(),
        patch_package=package,
        admission=admission,
        apply=args.apply,
        approval=approval,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ready_to_apply", "applied_verified"} else 1


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
