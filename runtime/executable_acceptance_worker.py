"""JSON worker entry point for process-isolated acceptance analysis."""

from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from .executable_acceptance import run_executable_acceptance


def main() -> int:
    payload = json.load(sys.stdin)
    with redirect_stdout(sys.stderr):
        result = run_executable_acceptance(
            root=Path(payload["root"]),
            project_dir=Path(payload["project_dir"]),
            test_plan=dict(payload["test_plan"]),
            work_dir=Path(payload["work_dir"]),
        )
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
