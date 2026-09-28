from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from runtime.self_development_corpus_eligibility import build_corpus_eligibility_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Index local corpora for untouched self-development evidence")
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_corpus_eligibility_index(root=Path(args.root), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "local_corpus_sufficient" else 2


if __name__ == "__main__":
    raise SystemExit(main())
