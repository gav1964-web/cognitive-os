from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.framework_plugin_holdout_selection import (
    build_framework_plugin_holdout_selection,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--eligibility", required=True)
    parser.add_argument("--external-candidates")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    eligibility = json.loads((root / args.eligibility).read_text(encoding="utf-8"))
    external = []
    if args.external_candidates:
        payload = json.loads((root / args.external_candidates).read_text(encoding="utf-8"))
        external = list(payload.get("projects") or [])
    report = build_framework_plugin_holdout_selection(
        root=root,
        eligibility=eligibility,
        external_candidates=external,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "local_corpus_sufficient" else 2


if __name__ == "__main__":
    raise SystemExit(main())
