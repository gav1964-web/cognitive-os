"""Validate a capability spec JSON file."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from foundry_admission import AdmissionError, check_candidate_spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="cos_spec_") as temp_dir:
        candidate_dir = Path(temp_dir) / str(spec["id"])
        candidate_dir.mkdir(parents=True)
        shutil.copy2(spec_path, candidate_dir / "spec.json")
        try:
            check_candidate_spec(candidate_dir, str(spec["id"]))
        except AdmissionError as exc:
            raise SystemExit(str(exc)) from exc
    print(json.dumps({"status": "ok", "spec": spec_path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
