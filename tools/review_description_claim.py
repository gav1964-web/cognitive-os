"""Prepare, run once, or attach a source-bound claim-review proposal."""
import argparse
import json
from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.single_claim_review import prepare_claim_review, run_claim_review
from runtime.claim_review_proposals import attach_proposals
from runtime.claim_review_decisions import record_review_decision
from runtime.claim_review_reporting import inspect_review, render_review
from runtime.project_description import description_model_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--report', required=True)
    prepare.add_argument('--claim-id', required=True)
    prepare.add_argument('--namespace', choices=['draft', 'final'], default='draft')
    prepare.add_argument('--return-flags', help='JSON list of path/symbol selectors for conditional suffix analysis')
    prepare.add_argument('--mechanism-review', action='store_true', help='Require explicit claim/predicate bindings and consistency checks')
    prepare.add_argument('--return-property', help='JSON selector: path, symbol, claim_start/end, kind; field, inputs and expected as required by kind')
    prepare.add_argument('--requests', help='JSON list of at most three hash-bound source lookups')
    prepare.add_argument('--coverage', help='JSON list of required evidence connections (id, description)')
    run = commands.add_parser('run')
    run.add_argument('--job', required=True)
    run.add_argument('--timeout', type=float, default=240)
    attach = commands.add_parser('attach')
    attach.add_argument('--audit', required=True)
    attach.add_argument('--proposal', action='append', required=True)
    attach.add_argument('--decisions', help='Separate source-bound reviewer decision ledger')
    decide = commands.add_parser('decide')
    decide.add_argument('--proposal', action='append', required=True)
    decide.add_argument('--ledger', help='Previous decision ledger; output must use a new path')
    decide.add_argument('--disposition', choices=['accepted', 'rejected', 'deferred'], required=True)
    decide.add_argument('--reviewer', required=True)
    decide.add_argument('--reason', required=True)
    decide.add_argument('--accepted-text', help='Exact candidate text explicitly accepted by reviewer')
    inspect = commands.add_parser('inspect')
    inspect.add_argument('--receipt', required=True)
    inspect.add_argument('--decisions')
    inspect.add_argument('--markdown', help='Optional human-readable report path')
    for sub in (prepare, run, attach, decide, inspect):
        sub.add_argument('--output', required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    target = Path(args.output)
    inputs = [getattr(args, key, None) for key in ('report', 'requests', 'return_flags', 'return_property', 'coverage', 'job', 'audit', 'ledger', 'decisions', 'receipt')]
    inputs += getattr(args, 'proposal', [])
    if any(target.resolve() == Path(path).resolve() for path in inputs if path):
        parser.error('output must differ from inputs')
    markdown = Path(args.markdown) if getattr(args, 'markdown', None) else None
    if markdown and any(markdown.resolve() == Path(path).resolve() for path in [*inputs, str(target)] if path):
        parser.error('markdown must differ from inputs and JSON output')
    # Do not re-spend a job's budget by silently overwriting an earlier receipt.
    if args.command in ('run', 'decide') and target.exists():
        parser.error('run/decision output already exists')
    try:
        if args.command == 'prepare':
            result = prepare_claim_review(read(args.report), args.claim_id,
                claim_namespace=args.namespace,
                return_flags=read(args.return_flags) if args.return_flags else None,
                mechanism_review=args.mechanism_review,
                return_property=read(args.return_property) if args.return_property else None,
                requests=read(args.requests) if args.requests else None,
                coverage_requirements=read(args.coverage) if args.coverage else None)
        elif args.command == 'decide':
            if len(args.proposal) != 1:
                parser.error('decide requires exactly one proposal')
            result = record_review_decision(read(args.proposal[0]), disposition=args.disposition,
                reviewer=args.reviewer, reason=args.reason, accepted_text=args.accepted_text,
                ledger=read(args.ledger) if args.ledger else None)
        elif args.command == 'attach':
            result = attach_proposals(read(args.audit), [read(path) for path in args.proposal],
                                      decisions=read(args.decisions) if args.decisions else None)
        elif args.command == 'inspect':
            result = inspect_review(read(args.receipt), decisions=read(args.decisions) if args.decisions else None)
        else:
            if not 0 < args.timeout <= 240:
                parser.error('timeout must be in (0, 240] seconds')
            result = run_claim_review(read(args.job), config=replace(description_model_config(),
                                                                    timeout_seconds=args.timeout))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Claim review failed: {exc}', file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_review(result), encoding='utf-8')
    print(json.dumps({'output': str(target), 'status': result.get('status', result.get('contract_status', 'prepared')),
                      'execution_authorized': False}))
    return 2 if result.get('status') == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
