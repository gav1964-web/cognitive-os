"""Manage dialogue memory records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--title", default="")
    create.add_argument("--topic", default="default")

    note = sub.add_parser("note")
    note.add_argument("--text", required=True)
    note.add_argument("--kind", default="note", choices=["note", "decision", "open_thread", "principle", "preference"])
    note.add_argument("--topic", default="default")
    note.add_argument("--dialogue-id", default=None)
    note.add_argument("--tag", action="append", default=[])

    turn = sub.add_parser("turn")
    turn.add_argument("--dialogue-id", required=True)
    turn.add_argument("--role", required=True, choices=["user", "assistant", "system"])
    turn.add_argument("--text", required=True)
    turn.add_argument("--topic", default=None)

    switch = sub.add_parser("switch-topic")
    switch.add_argument("--dialogue-id", required=True)
    switch.add_argument("--topic", required=True)

    recall = sub.add_parser("recall")
    recall.add_argument("--query", required=True)
    recall.add_argument("--limit", type=int, default=5)

    summary = sub.add_parser("summary")
    summary.add_argument("--dialogue-id", default=None)
    summary.add_argument("--topic", default=None)
    summary.add_argument("--limit", type=int, default=10)

    compact = sub.add_parser("compact")
    compact.add_argument("--dialogue-id", required=True)
    compact.add_argument("--keep-recent-turns", type=int, default=8)

    graph = sub.add_parser("topic-graph")
    graph.add_argument("--rebuild", action="store_true")

    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from runtime.dialogue_memory import DialogueMemory

    memory = DialogueMemory(Path(args.root).resolve())
    if args.command == "create":
        payload = {"status": "created", **memory.create_session(title=args.title, topic=args.topic)}
    elif args.command == "note":
        payload = {
            "status": "ok",
            "record": memory.note(
                text=args.text,
                kind=args.kind,
                topic=args.topic,
                dialogue_id=args.dialogue_id,
                tags=args.tag,
            ),
        }
    elif args.command == "turn":
        payload = {
            "status": "ok",
            "turn": memory.add_turn(args.dialogue_id, role=args.role, content=args.text, topic=args.topic),
        }
    elif args.command == "switch-topic":
        payload = {"status": "ok", **memory.switch_topic(args.dialogue_id, args.topic)}
    elif args.command == "recall":
        payload = {"status": "ok", **memory.recall(args.query, limit=args.limit)}
    elif args.command == "summary":
        payload = {"status": "ok", **memory.summary(dialogue_id=args.dialogue_id, topic=args.topic, limit=args.limit)}
    elif args.command == "compact":
        payload = {
            "status": "ok",
            "summary": memory.compact_session(args.dialogue_id, keep_recent_turns=args.keep_recent_turns),
        }
    elif args.command == "topic-graph":
        payload = {"status": "ok", **(memory.rebuild_topic_graph() if args.rebuild else memory.load_topic_graph())}
    else:
        raise AssertionError(args.command)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
