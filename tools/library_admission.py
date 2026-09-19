"""Explain source-backed library admission without executing repository code."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.library_admission import inspect_library_admission


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = inspect_library_admission(Path(args.project))
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded)
    return 0 if report["status"] == "admitted_candidate" else 2


if __name__ == "__main__":
    raise SystemExit(main())
