"""Begin/finish a development stage, manage pending work and record decisions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from runtime.development_stage import begin_stage, finish_stage
    from runtime.development_work_items import put_work_item, close_work_item, KINDS
    from runtime.development_decisions import remember_decision
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    commands = parser.add_subparsers(dest='command', required=True)
    begin = commands.add_parser('begin')
    begin.add_argument('--path', action='append')
    finish = commands.add_parser('finish')
    finish.add_argument('--test-target', action='append', required=True)
    finish.add_argument('--pytest-plugin', action='append', default=[])
    finish.add_argument('--timeout', type=int, default=180)
    finish.add_argument('--summary', default='')
    task = commands.add_parser('task')
    task.add_argument('--key', required=True)
    task.add_argument('--kind', choices=sorted(KINDS), required=True)
    task.add_argument('--path', required=True)
    task.add_argument('--next-action', required=True)
    task.add_argument('--blocking', action='store_true')
    task.add_argument('--priority', type=int, choices=[1, 2, 3], default=2)
    task.add_argument('--depends-on', action='append', default=[])
    close = commands.add_parser('close')
    close.add_argument('--id', required=True)
    close.add_argument('--evidence', action='append', required=True)
    close.add_argument('--summary', required=True)
    decision = commands.add_parser('remember')
    decision.add_argument('--key', required=True)
    decision.add_argument('--decision', required=True)
    decision.add_argument('--rationale', required=True)
    decision.add_argument('--path', action='append', required=True)
    decision.add_argument('--reconsider-when', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == 'begin':
        result = begin_stage(root, paths=args.path)
    elif args.command == 'finish':
        result = finish_stage(root, test_targets=args.test_target, pytest_plugins=args.pytest_plugin,
                              timeout=args.timeout, summary=args.summary)
    elif args.command == 'task':
        result = put_work_item(root, key=args.key, kind=args.kind, path=args.path,
                               next_action=args.next_action, blocking=args.blocking,
                               priority=args.priority, dependencies=args.depends_on)
    elif args.command == 'close':
        result = close_work_item(root, args.id, evidence=args.evidence, summary=args.summary)
    else:
        result = remember_decision(root, key=args.key, decision=args.decision, rationale=args.rationale,
                                   paths=args.path, reconsider_when=args.reconsider_when)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.command == 'finish' and result['status'] != 'completed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
