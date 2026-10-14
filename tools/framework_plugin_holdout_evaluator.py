from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.framework_plugin_holdout_evaluator import evaluate_framework_plugin_holdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", required=True)
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--stub-audit", required=True)
    parser.add_argument("--role-regression", required=True)
    parser.add_argument("--holdout-report", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = {
        "selection": Path(args.selection),
        "evaluation": Path(args.evaluation),
        "stub_audit": Path(args.stub_audit),
        "role_regression": Path(args.role_regression),
    }
    reports = [Path(value).resolve() for value in args.holdout_report]
    payloads = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    holdouts = [json.loads(path.read_text(encoding="utf-8")) for path in reports]
    report_digests = {path.as_posix(): _file_digest(path) for path in reports}
    input_digests = {
        **{name: _file_digest(path.resolve()) for name, path in paths.items()},
        **{f"holdout:{path.name}": digest for path, digest in zip(reports, report_digests.values())},
    }
    evidence = evaluate_framework_plugin_holdout(
        selection=payloads["selection"],
        evaluation=payloads["evaluation"],
        holdout_reports=holdouts,
        report_digests=report_digests,
        stub_audit=payloads["stub_audit"],
        role_regression=payloads["role_regression"],
        input_digests=input_digests,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "passed" else 2


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
