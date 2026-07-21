"""Manage staged KnowledgeCandidate artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.knowledge_admission import (
    build_manual_merge_block,
    grouped_candidate_report,
    knowledge_candidate_report,
    load_kb_candidates,
    update_kb_candidate_review,
    write_kb_candidate,
)
from runtime.knowledge_review_console import build_knowledge_review_console


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage staged Cognitive OS knowledge candidates.")
    parser.add_argument("--root", default=".", help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    write_parser = sub.add_parser("write", help="write a candidate JSON into artifacts/knowledge_candidates")
    write_parser.add_argument("--candidate", required=True, help="path to candidate JSON")

    report_parser = sub.add_parser("report", help="print candidate review report")
    report_parser.add_argument("--grouped", action="store_true", help="group candidates by proposed record id")
    sub.add_parser("review", help="print review queues for staged candidates")
    approve_teacher = sub.add_parser("approve-teacher", help="mark a candidate as teacher-approved")
    approve_teacher.add_argument("--candidate-id", required=True)
    approve_codex = sub.add_parser("approve-codex", help="mark a candidate as Codex/developer-approved")
    approve_codex.add_argument("--candidate-id", required=True)
    reject = sub.add_parser("reject", help="reject a staged candidate")
    reject.add_argument("--candidate-id", required=True)
    reject.add_argument("--reason", required=True)
    merge = sub.add_parser("merge", help="show controlled manual-merge block for a candidate")
    merge.add_argument("--candidate-id", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.command == "write":
        candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        path = write_kb_candidate(candidate, root=root)
        print(json.dumps({"status": "ok", "path": path.as_posix()}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "report":
        candidates = load_kb_candidates(root=root)
        report = grouped_candidate_report(candidates) if args.grouped else knowledge_candidate_report(candidates)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "review":
        report = build_knowledge_review_console(root=root)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "approve-teacher":
        report = update_kb_candidate_review(root=root, candidate_id=args.candidate_id, teacher_approved=True)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "approve-codex":
        report = update_kb_candidate_review(root=root, candidate_id=args.candidate_id, codex_approved=True)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "reject":
        report = update_kb_candidate_review(root=root, candidate_id=args.candidate_id, rejected_reason=args.reason)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "merge":
        report = build_manual_merge_block(root=root, candidate_id=args.candidate_id)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
