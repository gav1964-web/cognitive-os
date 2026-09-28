from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.recovery_boundary_experiment import evaluate_recovery_boundary_experiments


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate evidence for semantic recovery boundaries")
    parser.add_argument("research_report")
    parser.add_argument("--evidence")
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    research = json.loads(Path(args.research_report).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8")) if args.evidence else []
    if isinstance(evidence, dict):
        evidence = evidence.get("cases", [])
    report = evaluate_recovery_boundary_experiments(
        research,
        evidence_cases=evidence,
        root=Path(args.root).resolve(),
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"admitted", "evidence_required"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
