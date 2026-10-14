"""Run nested callable-scope analysis over a local corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.source_scope_field_trial import run_source_scope_field_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--max-samples", type=int, default=40)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    corpus = Path(args.corpus_dir)
    if not corpus.is_absolute():
        corpus = root / corpus
    report = run_source_scope_field_trial(
        corpus_dir=corpus,
        max_samples=max(0, args.max_samples),
        write_root=root if args.write else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
