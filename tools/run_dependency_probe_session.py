"""Run a bounded dependency chain from saved profile and session approval artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.dependency_probe_session import run_dependency_probe_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--session-approval", required=True)
    args = parser.parse_args()
    result = run_dependency_probe_session(
        workspace_root=Path(args.root),
        initial_profile=_read_object(Path(args.profile)),
        session=_read_object(Path(args.session_approval)),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "passed" else 1


def _read_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
