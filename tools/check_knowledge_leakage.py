"""Check that decision-bearing Spec Writer scores stay in KB."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.spec_writer_ranking_kb import knowledge_leakage_violations


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    violations = knowledge_leakage_violations(root)
    print(json.dumps({"status": "failed" if violations else "ok", "violations": violations}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
