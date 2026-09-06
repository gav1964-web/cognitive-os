"""Evaluate paired role and execution runs for narrow semantic certification."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.narrow_type_role_semantics import evaluate_narrow_type_role_semantics


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    manifest = _read(_resolve(root, args.manifest))
    cases = []
    for row in manifest.get("cases") or []:
        case = dict(row)
        case["role_run"] = _read(_resolve(root, str(row["role_report"])))
        case["execution_run"] = _read(_resolve(root, str(row["execution_report"])))
        cases.append(case)
    report = evaluate_narrow_type_role_semantics(
        cases=cases,
        evaluation_split=str(manifest.get("evaluation_split") or "calibration"),
    )
    if args.write or args.summary:
        directory = root / "artifacts" / "self_development"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = directory / f"narrow_type_role_semantics_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.relative_to(root).as_posix()
    output = report
    if args.write:
        output = {
            "artifact_type": report["artifact_type"],
            "status": report["status"],
            "evaluation_split": report["evaluation_split"],
            "role_scores": report["role_scores"],
            "checks": report["checks"],
            "failed_checks": report["failed_checks"],
            "report_path": report["report_path"],
            "evidence_digest": report["evidence_digest"],
        }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
