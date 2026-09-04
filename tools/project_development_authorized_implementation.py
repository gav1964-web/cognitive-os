"""Run one digest-authorized project implementation in a non-applying sandbox."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_development import load_project_development_policy
from runtime.project_development_authorized_implementation import run_authorized_implementation
from runtime.project_development_implementation_authorization import (
    build_implementation_authorization_request,
    validate_implementation_authorization,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--design-report", required=True)
    parser.add_argument("--human-approval")
    parser.add_argument("--failing-nodeid", action="append", default=[])
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    project = _resolve(root, args.project_dir)
    design = _read(_resolve(root, args.design))
    report = _read(_resolve(root, args.design_report))
    design_validation = dict(
        dict(report.get("feedback_continuation") or {}).get("implementation_design_validation") or {}
    )
    policy = load_project_development_policy()
    request = build_implementation_authorization_request(
        design=design,
        design_validation=design_validation,
        policy=policy,
    )
    human = _read(_resolve(root, args.human_approval)) if args.human_approval else None
    validation = validate_implementation_authorization(
        request=request,
        human_decision=human,
        design=design,
        design_validation=design_validation,
        policy=policy,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result = None
    if args.run:
        result = run_authorized_implementation(
            root=root,
            project_dir=project,
            execution_dir=root / "artifacts" / "project_development" / "authorized_implementations" / stamp,
            design=design,
            authorization_validation=validation,
            failing_nodeids=list(args.failing_nodeid),
            policy=policy,
        )
    payload = {
        "artifact_type": "ProjectDevelopmentAuthorizedImplementationRun",
        "status": (
            str(result.get("status")) if result is not None else
            "awaiting_human_approval" if validation.get("status") == "pending" else
            "authorized" if validation.get("status") == "approved" else "blocked"
        ),
        "authorization_request": request,
        "human_decision": human,
        "authorization_validation": validation,
        "implementation_result": result,
        "source_apply": False,
        "memory_promotion": False,
    }
    if args.write:
        path = root / "artifacts" / "project_development" / f"authorized_implementation_{stamp}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["report_path"] = path.as_posix()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] in {
        "awaiting_human_approval", "authorized", "verified_in_sandbox"
    } else 1


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _read(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
