from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.narrow_type_holdout_evaluator import evaluate_narrow_type_holdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--role-pipeline", required=True)
    parser.add_argument("--stub-audit")
    parser.add_argument("--output")
    args = parser.parse_args()
    evaluation = _read(Path(args.evaluation))
    role_pipeline = _read(Path(args.role_pipeline))
    stub_audit = _read(Path(args.stub_audit)) if args.stub_audit else None
    report = evaluate_narrow_type_holdout(
        evaluation=evaluation,
        role_pipeline_report=role_pipeline,
        stub_audit=stub_audit,
    )
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
    print(encoded.decode("utf-8"), end="")
    return 0 if report["status"] == "passed" else 2


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
