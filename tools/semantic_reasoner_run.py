"""Run the bounded L4.5 semantic reasoner on a request JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.local_inference import LocalInferenceConfig
    from runtime.semantic_reasoner import build_stage2_template_backlog_item, run_semantic_reasoner

    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--write-backlog", action="store_true")
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument("--base-url", default=os.environ.get("COGNITIVE_OS_L45_BASE_URL", os.environ.get("COGNITIVE_OS_L4_BASE_URL", "http://127.0.0.1:8000/v1")))
    parser.add_argument("--model", default=os.environ.get("COGNITIVE_OS_L45_MODEL", os.environ.get("COGNITIVE_OS_L4_MODEL", "GigaChat-Pro")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("COGNITIVE_OS_L45_TIMEOUT", os.environ.get("COGNITIVE_OS_L4_TIMEOUT", "120"))))
    parser.add_argument("--api-key-env", default=os.environ.get("COGNITIVE_OS_L45_API_KEY_ENV", os.environ.get("COGNITIVE_OS_L4_API_KEY_ENV", "COGNITIVE_OS_L4_API_KEY")))
    args = parser.parse_args()

    request_path = Path(args.request_json).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    config = LocalInferenceConfig(
        base_url=args.base_url.rstrip("/"),
        model=args.model,
        timeout_seconds=args.timeout,
        api_key=os.environ.get(args.api_key_env) or None,
        provider_label="external_l45",
    )
    proposal = run_semantic_reasoner(request=request, config=config, use_model=args.use_model)
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
