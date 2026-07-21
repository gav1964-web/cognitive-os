"""Run the L4.0/L4.5 semantic-loop benchmark."""

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

    from runtime.l45_semantic_benchmark import run_l45_semantic_benchmark
    from runtime.local_inference import LocalInferenceConfig

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--generated-corpus-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=45)
    parser.add_argument(
        "--corpus-profile",
        choices=["balanced", "risk_heavy", "unknown_template_heavy", "known_template_regression"],
        default="balanced",
    )
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument(
        "--model-quality-mode",
        choices=["deterministic", "model_propose_only", "model_with_human_review", "blocked_model_untrusted"],
        default=None,
    )
    default_l45 = LocalInferenceConfig.from_l45_env()
    parser.add_argument("--base-url", default=default_l45.base_url)
    parser.add_argument("--model", default=default_l45.model)
    parser.add_argument("--timeout", type=float, default=default_l45.timeout_seconds)
    parser.add_argument("--api-key-env", default=os.environ.get("COGNITIVE_OS_L45_API_KEY_ENV", "COGNITIVE_OS_L45_API_KEY"))
    args = parser.parse_args()

    config = LocalInferenceConfig(
        base_url=args.base_url.rstrip("/"),
        model=args.model,
        timeout_seconds=args.timeout,
        api_key=os.environ.get(args.api_key_env) or None,
        provider_label="external_l45",
    )
    report = run_l45_semantic_benchmark(
        root=Path(args.root).resolve(),
        write=args.write,
        use_model=args.use_model,
        model_quality_mode=args.model_quality_mode,
        config=config,
        generated_corpus_size=args.generated_corpus_size,
        seed=args.seed,
        corpus_profile=args.corpus_profile,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
