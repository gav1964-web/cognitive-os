"""Import selected external sources into staged KB candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.knowledge_admission import knowledge_candidate_report, load_kb_candidates, write_kb_candidate
from runtime.knowledge_import import fetch_pypi_metadata, official_docs_fact_candidate, pypi_candidate_from_metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Import PyPI and official-docs evidence into staged KB candidates.")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--pypi", nargs="*", default=[], help="PyPI package names")
    parser.add_argument(
        "--official-doc",
        action="append",
        default=[],
        help="official docs spec: url|question|needed_for",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    written = []
    skipped = []
    failures = []

    for package in args.pypi:
        try:
            metadata = fetch_pypi_metadata(package)
            candidate = pypi_candidate_from_metadata(metadata)
            if candidate is None:
                skipped.append({"source": "pypi", "package": package, "reason": "no matching archetype rule"})
                continue
            path = write_kb_candidate(candidate, root=root)
            written.append({"source": "pypi", "package": package, "path": path.as_posix(), "status": candidate["status"]})
        except Exception as exc:  # pragma: no cover - exercised by real CLI/network
            failures.append({"source": "pypi", "package": package, "error": repr(exc)})

    for spec in args.official_doc:
        try:
            url, question, needed_for = _split_doc_spec(spec)
            candidate = official_docs_fact_candidate(url=url, question=question, needed_for=needed_for)
            path = write_kb_candidate(candidate, root=root)
            written.append({"source": "official_docs", "url": url, "path": path.as_posix(), "status": candidate["status"]})
        except Exception as exc:  # pragma: no cover - exercised by real CLI/network
            failures.append({"source": "official_docs", "spec": spec, "error": repr(exc)})

    report = knowledge_candidate_report(load_kb_candidates(root=root))
    print(
        json.dumps(
            {
                "status": "ok" if not failures else "partial",
                "written": written,
                "skipped": skipped,
                "failures": failures,
                "candidate_report": report,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


def _split_doc_spec(spec: str) -> tuple[str, str, str]:
    parts = spec.split("|", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError("official-doc spec must be: url|question|needed_for")
    return parts[0].strip(), parts[1].strip(), parts[2].strip()


if __name__ == "__main__":
    raise SystemExit(main())
