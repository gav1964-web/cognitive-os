"""Interpret a deterministic project-analysis report with a local LLM."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from tools.l4_defaults import l4_base_url, l4_model
except ModuleNotFoundError:  # Direct `python tools/interpret_project_report.py` execution.
    from l4_defaults import l4_base_url, l4_model


LOCAL_L4_FORBIDDEN_MODELS = {
    "local",
    "qwen-local",
    "qwen-local-cpu",
    "fast-local-cpu",
    "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="local")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--no-response-format", action="store_true")
    parser.add_argument("--l4-base-url", default=l4_base_url())
    parser.add_argument("--l4-model", default=l4_model())
    parser.add_argument("--l4-timeout", type=float, default=float(os.environ.get("COGNITIVE_OS_L4_TIMEOUT", "120")))
    parser.add_argument("--l4-api-key-env", default=os.environ.get("COGNITIVE_OS_L4_API_KEY_ENV", "COGNITIVE_OS_L4_API_KEY"))
    parser.add_argument("--l4-no-response-format", action="store_true")
    parser.add_argument("--l4-context", choices=["expanded", "compact"], default=os.environ.get("COGNITIVE_OS_L4_CONTEXT", "expanded"))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
    from runtime.project_interpreter import interpret_project_report

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = root / report_path
    report = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        signal_config = LocalInferenceConfig(
            base_url=args.base_url.rstrip("/"),
            model=args.model,
            timeout_seconds=args.timeout,
            response_format=not args.no_response_format,
            provider_label="local",
        )
        cortex_config = None
        if args.l4_model and args.l4_model not in LOCAL_L4_FORBIDDEN_MODELS:
            cortex_config = LocalInferenceConfig(
                base_url=(args.l4_base_url or args.base_url).rstrip("/"),
                model=args.l4_model,
                timeout_seconds=args.l4_timeout,
                response_format=not args.l4_no_response_format,
                api_key=os.environ.get(args.l4_api_key_env) if args.l4_api_key_env else None,
                provider_label="external_l4",
            )
        interpretation = interpret_project_report(
            report,
            signal_config=signal_config,
            cortex_config=cortex_config,
            context_mode=args.l4_context,
        )
    except LocalInferenceError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    output_path = Path(args.output) if args.output else report_path.with_suffix(".interpretation.json")
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": output_path.as_posix(), "interpretation": interpretation}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
