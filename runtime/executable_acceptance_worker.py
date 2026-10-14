"""JSON worker entry point for process-isolated acceptance analysis."""

from __future__ import annotations

import json
import sys
from contextlib import nullcontext, redirect_stdout
from pathlib import Path

from .executable_acceptance import run_executable_acceptance
from .executable_acceptance_policy import temporary_executable_acceptance_policy


def main() -> int:
    payload = json.load(sys.stdin)
    policy = payload.get("executable_policy")
    context = temporary_executable_acceptance_policy(policy) if policy else nullcontext()
    with context, redirect_stdout(sys.stderr):
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
