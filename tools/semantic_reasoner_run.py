"""Run the bounded L4.5 semantic reasoner on a request JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.semantic_reasoner import build_stage2_template_backlog_item, run_semantic_reasoner

    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--write-backlog", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.request_json).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    proposal = run_semantic_reasoner(request=request)
    result = {"status": proposal.get("status"), "proposal": proposal}
    backlog = build_stage2_template_backlog_item(proposal)
    if backlog is not None:
        result["stage2_template_backlog_item"] = backlog
        if args.write_backlog:
            out_dir = repo_root / "artifacts" / "stage2_template_backlog"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{backlog['template_id']}.json"
            out_path.write_text(json.dumps(backlog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result["backlog_path"] = out_path.as_posix()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if proposal.get("status") in {"ok", "blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
