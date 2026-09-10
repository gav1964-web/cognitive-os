"""Freeze local wheel identities for a public qualification campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.historical_defect_environment import freeze_environment_profile
from runtime.local_historical_defect_evidence import evidence_digest, inside


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--public", required=True)
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument("--candidate-id", action="append")
    parser.add_argument("--pytest-plugin", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    public = json.loads(inside(root, args.public).read_text(encoding="utf-8"))
    body = {key: value for key, value in public.items() if key != "manifest_digest"}
    if public.get("manifest_digest") != evidence_digest(body):
        raise ValueError("public manifest digest mismatch")
    case_ids = {row["candidate_id"] for row in public["cases"]}
    selected = set(args.candidate_id or case_ids)
    if not selected or not selected.issubset(case_ids):
        raise ValueError("environment selection is outside the public campaign")
    profile = freeze_environment_profile(
        root=root, wheels=list(inside(root, args.wheelhouse).glob("*.whl")),
        pytest_plugins=args.pytest_plugin,
    )
    bundle = {"schema_version": "historical_defect_environment_bundle.v1",
              "public_manifest_digest": public["manifest_digest"],
              "profiles": {case_id: profile for case_id in sorted(selected)}}
    bundle["bundle_digest"] = evidence_digest(bundle)
    output = inside(root, args.output)
    if output == inside(root, args.public):
        raise ValueError("environment output must not overwrite the frozen public manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "frozen", "output": output.relative_to(root).as_posix(),
                      "bundle_digest": bundle["bundle_digest"], "cases": len(selected)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
