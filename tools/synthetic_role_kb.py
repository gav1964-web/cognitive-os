"""Generate and inspect synthetic role-scoped Q/A seed corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.synthetic_role_kb import (
    load_synthetic_role_qa,
    record_role_qa_feedback,
    search_synthetic_role_qa,
    synthetic_role_qa_audit,
    synthetic_probe_report,
    synthetic_role_qa_summary,
    write_llm_role_qa,
    write_synthetic_role_qa,
)
from runtime.local_inference import LocalInferenceConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic role KB seed corpus")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate")
    generate.add_argument("--records-per-role", type=int, default=None)
    generate.add_argument("--output", default=None)

    generate_llm = sub.add_parser("generate-llm")
    generate_llm.add_argument("--records-per-role", type=int, default=20)
    generate_llm.add_argument("--output", default=None)
    generate_llm.add_argument("--replace", action="store_true", help="Do not append to an existing corpus")
    generate_llm.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    generate_llm.add_argument("--model", default="deepseek/deepseek-chat")
    generate_llm.add_argument("--timeout", type=float, default=120.0)
    generate_llm.add_argument("--no-response-format", action="store_true")

    summary = sub.add_parser("summary")
    summary.add_argument("--corpus", default=None)

    search = sub.add_parser("search")
    search.add_argument("--corpus", default=None)
    search.add_argument("--role-id", default=None)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=5)

    probe = sub.add_parser("probe")
    probe.add_argument("--corpus", default=None)

    audit = sub.add_parser("audit")
    audit.add_argument("--corpus", default=None)

    feedback = sub.add_parser("feedback")
    feedback.add_argument("--corpus", default=None)
    feedback.add_argument("--qa-id", required=True)
    feedback.add_argument("--outcome", choices=["positive", "negative"], required=True)
    feedback.add_argument("--case-id", default=None)
    feedback.add_argument("--note", default=None)

    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == "generate":
        output = Path(args.output) if args.output else None
        if output is not None and not output.is_absolute():
            output = root / output
        path = write_synthetic_role_qa(root=root, output=output, records_per_role=args.records_per_role)
        corpus = load_synthetic_role_qa(path)
        print(json.dumps({"status": "ok", "path": path.as_posix(), **synthetic_role_qa_summary(corpus)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "generate-llm":
        output = Path(args.output) if args.output else None
        if output is not None and not output.is_absolute():
            output = root / output
        config = LocalInferenceConfig(
            base_url=args.base_url.rstrip("/"),
            model=args.model,
            timeout_seconds=args.timeout,
            response_format=not args.no_response_format,
            provider_label="llm_role_qa_generator",
        )
        path = write_llm_role_qa(
            root=root,
            output=output,
            records_per_role=args.records_per_role,
            append=not args.replace,
            config=config,
        )
        corpus = load_synthetic_role_qa(path)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "path": path.as_posix(),
                    "model": args.model,
                    "base_url": args.base_url,
                    **synthetic_role_qa_summary(corpus),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "summary":
        corpus = load_synthetic_role_qa(Path(args.corpus) if args.corpus else None)
        print(json.dumps(synthetic_role_qa_summary(corpus), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "search":
        corpus = load_synthetic_role_qa(Path(args.corpus) if args.corpus else None)
        print(
            json.dumps(
                search_synthetic_role_qa(args.query, role_id=args.role_id, corpus=corpus, limit=args.limit),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "probe":
        corpus = load_synthetic_role_qa(Path(args.corpus) if args.corpus else None)
        print(json.dumps(synthetic_probe_report(corpus), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "audit":
        corpus = load_synthetic_role_qa(Path(args.corpus) if args.corpus else None)
        report = synthetic_role_qa_audit(corpus)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["status"] == "ok" else 1
    if args.command == "feedback":
        report = record_role_qa_feedback(
            qa_id=args.qa_id,
            outcome=args.outcome,
            case={"case_id": args.case_id, "note": args.note},
            path=Path(args.corpus) if args.corpus else None,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
