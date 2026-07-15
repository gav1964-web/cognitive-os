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

    from runtime.l4_semantic_validation import validate_l45_semantic_proposal
    from runtime.l45_model_modes import resolve_model_quality_mode
    from runtime.local_inference import LocalInferenceConfig
    from runtime.semantic_evidence_pack import build_semantic_evidence_pack
    from runtime.semantic_reasoner import build_stage2_template_backlog_item, run_semantic_reasoner
    from runtime.semantic_replay import build_semantic_replay_record, write_semantic_replay_record

    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--write-backlog", action="store_true")
    parser.add_argument("--write-replay", action="store_true")
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument(
        "--model-quality-mode",
        choices=["deterministic", "model_propose_only", "model_with_human_review", "blocked_model_untrusted"],
        default=None,
    )
    parser.add_argument("--base-url", default=os.environ.get("COGNITIVE_OS_L45_BASE_URL", os.environ.get("COGNITIVE_OS_L4_BASE_URL", "http://127.0.0.1:8000/v1")))
    parser.add_argument("--model", default=os.environ.get("COGNITIVE_OS_L45_MODEL", os.environ.get("COGNITIVE_OS_L4_MODEL", "GigaChat-Pro")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("COGNITIVE_OS_L45_TIMEOUT", os.environ.get("COGNITIVE_OS_L4_TIMEOUT", "120"))))
    parser.add_argument("--api-key-env", default=os.environ.get("COGNITIVE_OS_L45_API_KEY_ENV", os.environ.get("COGNITIVE_OS_L4_API_KEY_ENV", "COGNITIVE_OS_L4_API_KEY")))
    args = parser.parse_args()

    request_path = Path(args.request_json).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    policy = resolve_model_quality_mode(args.model_quality_mode, use_model_flag=args.use_model)
    config = LocalInferenceConfig(
        base_url=args.base_url.rstrip("/"),
        model=args.model,
        timeout_seconds=args.timeout,
        api_key=os.environ.get(args.api_key_env) or None,
        provider_label="external_l45",
    )
    if policy["mode"] == "blocked_model_untrusted":
        result = {
            "status": "blocked",
            "model_quality_mode": policy["mode"],
            "blocker": "model path is intentionally blocked by quality mode",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    proposal = run_semantic_reasoner(request=request, config=config, use_model=bool(policy["use_model"]))
    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)
    evidence_pack = build_semantic_evidence_pack(
        control_plane_decision=dict(request.get("source_decision", {})),
        context={"request_json": request_path.as_posix()},
    )
    result = {
        "status": validation.get("status"),
        "model_quality_mode": policy["mode"],
        "proposal": proposal,
        "l4_semantic_validation": validation,
    }
    backlog = (
        build_stage2_template_backlog_item(proposal)
        if validation.get("accepted_action") == "record_template_backlog"
        else None
    )
    if backlog is not None:
        result["stage2_template_backlog_item"] = backlog
        if args.write_backlog:
            out_dir = repo_root / "artifacts" / "stage2_template_backlog"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{backlog['template_id']}.json"
            out_path.write_text(json.dumps(backlog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result["backlog_path"] = out_path.as_posix()
    if args.write_replay:
        replay = build_semantic_replay_record(
            request=request,
            proposal=proposal,
            validation=validation,
            evidence_pack=evidence_pack,
            model_quality_mode=str(policy["mode"]),
            outcome={"stage2_template_backlog_item": backlog},
        )
        result["replay_path"] = write_semantic_replay_record(repo_root, replay).as_posix()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation.get("status") in {"accepted", "blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
