"""Run multi-profile L4.5 semantic evaluation suite."""

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

    from runtime.l45_semantic_eval_suite import DEFAULT_PROFILES, run_l45_semantic_evaluation_suite
    from runtime.local_inference import LocalInferenceConfig

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--generated-corpus-size", type=int, default=50)
    parser.add_argument("--seed", type=int, default=45)
    parser.add_argument("--profiles", nargs="+", default=list(DEFAULT_PROFILES))
    parser.add_argument("--include-model", action="store_true")
    parser.add_argument(
        "--model-quality-mode",
        choices=["model_propose_only", "model_with_human_review"],
        default="model_propose_only",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--base-url", default=os.environ.get("COGNITIVE_OS_L45_BASE_URL", os.environ.get("COGNITIVE_OS_L4_BASE_URL", "http://127.0.0.1:8000/v1")))
    parser.add_argument("--model", default=os.environ.get("COGNITIVE_OS_L45_MODEL", "GigaChat Lite"))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("COGNITIVE_OS_L45_TIMEOUT", os.environ.get("COGNITIVE_OS_L4_TIMEOUT", "120"))))
    parser.add_argument("--api-key-env", default=os.environ.get("COGNITIVE_OS_L45_API_KEY_ENV", os.environ.get("COGNITIVE_OS_L4_API_KEY_ENV", "COGNITIVE_OS_L4_API_KEY")))
    args = parser.parse_args()

    config = LocalInferenceConfig(
        base_url=args.base_url.rstrip("/"),
        model=args.model,
        timeout_seconds=args.timeout,
        api_key=os.environ.get(args.api_key_env) or None,
        provider_label="external_l45",
    )
    report = run_l45_semantic_evaluation_suite(
        root=Path(args.root).resolve(),
        generated_corpus_size=args.generated_corpus_size,
        seed=args.seed,
        profiles=list(args.profiles),
        include_model=args.include_model,
        model_quality_mode=args.model_quality_mode,
        config=config,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
