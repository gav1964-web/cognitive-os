"""Check a development stage or finalize supported splits with verified LLM plans."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.stage_finalization import finalize_stage
from runtime.development_handoff import sync_handoff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--phase', choices=['development', 'final'], default='final')
    parser.add_argument('--repair', action='store_true', help='Ask configured L4.5 LLM for bounded function groups')
    parser.add_argument('--apply', action='store_true', help='Apply only after baseline and sandbox verification pass')
    parser.add_argument('--test-target', action='append', default=[], help='Explicit regression directory/file; repeatable')
    parser.add_argument('--pytest-plugin', action='append', default=[])
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--output', help='Write complete JSON receipt')
    parser.add_argument('--no-handoff', action='store_true', help='Do not update the project assistant queue (isolated audits)')
    args = parser.parse_args()
    if args.apply and not args.repair:
        parser.error('--apply requires --repair')
    if args.repair and args.phase != 'final':
        parser.error('--repair requires --phase final')
    if args.timeout < 1:
        parser.error('--timeout must be positive')
    report = finalize_stage(Path(args.root), repair=args.repair, apply=args.apply, phase=args.phase,
                            test_targets=args.test_target, pytest_plugins=args.pytest_plugin, timeout=args.timeout)
    if not args.no_handoff:
        try:
            report['handoff'] = sync_handoff(Path(args.root), report, repair=args.repair,
                                           test_targets=args.test_target, pytest_plugins=args.pytest_plugin)
            if report['handoff'].get('blocking_pending') and report['stage_complete']:
                report.update(status='needs_handoff_review', stage_complete=False, blocking=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report['handoff'] = {'status': 'failed', 'error_kind': type(exc).__name__}
            report.update(status='handoff_failed', stage_complete=False, blocking=True)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded + '\n', encoding='utf-8')
    print(encoded)
    return 1 if report['blocking'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
