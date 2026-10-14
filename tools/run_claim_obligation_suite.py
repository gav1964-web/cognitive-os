"""Run a frozen five-case protocol once, with persisted attempts and no retries."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.single_claim_review import checked_job, review_messages, run_claim_review
from runtime.project_description import description_model_config
from runtime.narrow_type_evidence_binding import content_digest
from runtime.claim_suite_budget import check_budget, start_call, settle_call


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    # Replace a complete progress snapshot; a crash never authorizes retry.
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def preflight(protocol_path):
    protocol_path = Path(protocol_path).resolve()
    protocol = read(protocol_path)
    required = {'schema_version': 'claim_obligation_protocol.v1', 'proposed_max_requests': 5,
                'max_requests_per_case': 1, 'timeout_seconds': 240, 'retries': 0,
                'fallbacks': False, 'max_completion_tokens_per_request': 3200}
    if any(protocol.get(key) != value for key, value in required.items()):
        raise ValueError('suite_budget_or_contract_changed')
    cases = protocol.get('cases')
    version = protocol.get('review_version', 2)
    if type(version) is not int or version not in (2, 3, 4):
        raise ValueError('suite_review_version_invalid')
    if not isinstance(cases, list) or len(cases) != 5:
        raise ValueError('suite_requires_five_cases')
    jobs, names, digests = [], set(), set()
    for row in cases:
        name = row.get('case')
        if not isinstance(name, str) or not re.fullmatch(r'case\d{2}', name) or name in names:
            raise ValueError('suite_invalid_case')
        path = (protocol_path.parent / row['job']).resolve()
        if not path.is_relative_to(protocol_path.parent):
            raise ValueError('suite_job_outside_protocol')
        job = read(path)
        checked_job(job)
        messages = review_messages(job)
        if (job['schema_version'] != f'single_claim_review_job.v{version}' or job['digest'] != row['job_digest']
                or content_digest(messages) != row['messages_digest'] or job['digest'] in digests
                or sum(len(m['content']) for m in messages) != row['request_characters']):
            raise ValueError('suite_frozen_input_changed')
        names.add(name)
        digests.add(job['digest'])
        jobs.append((name, job))
    return protocol, jobs


def run_suite(protocol_path, output, *, budget_reference, config=None, chat=None, progress=None, token_budget=None):
    if not isinstance(budget_reference, str) or not budget_reference.strip():
        raise ValueError('suite_budget_reference_required')
    protocol_path, output = Path(protocol_path).resolve(), Path(output).resolve()
    protocol, jobs = preflight(protocol_path)
    if protocol.get('review_version', 2) >= 3 and token_budget is None:
        raise ValueError('suite_token_budget_required')
    if token_budget is not None:
        check_budget(token_budget, [job for _, job in jobs])
    cfg = replace(config or description_model_config(), timeout_seconds=240, fallbacks=())
    if cfg.model != 'deepseek/deepseek-v3.2':
        raise ValueError('suite_model_changed')
    if output.exists():
        raise ValueError('suite_output_already_exists')
    marker = protocol_path.with_name('execution.json')
    authorization = {'protocol_digest': content_digest(protocol), 'output': str(output),
                     'budget_reference': budget_reference, 'max_requests': 5,
                     'token_budget': str(Path(token_budget).resolve()) if token_budget else None,
                     'started_at': datetime.now(timezone.utc).isoformat()}
    # Exclusive creation prevents simultaneous runs and accidental resumption in
    # a different output directory. This records caller authorization, not a signature.
    with marker.open('x', encoding='utf-8') as stream:
        json.dump(authorization, stream, ensure_ascii=False, indent=2)
    output.mkdir(parents=True)
    state = {'schema_version': 'claim_suite_run.v1', 'status': 'running',
             **authorization, 'attempts': [], 'budget_closed': False}
    write(output / 'progress.json', state)
    for name, job in jobs:
        if token_budget is not None:
            try:
                start_call(token_budget, job)
            except ValueError as exc:
                state['stop_reason'] = str(exc)
                break
        attempt = {'case': name, 'status': 'started', 'job_digest': job['digest']}
        state['attempts'].append(attempt)
        write(output / 'progress.json', state)
        if progress:
            progress(dict(attempt))
        try:
            receipt = run_claim_review(job, config=cfg, chat=chat)
            write(output / f'{name}_result.json', receipt)
            if token_budget is not None:
                known = settle_call(token_budget, job, receipt['telemetry'])
                if not known:
                    state['stop_reason'] = 'budget_unresolved_usage'
            attempt.update(status=receipt['status'], reason=receipt.get('reason'),
                verdict=receipt.get('result', {}).get('verdict'),
                reported_tokens=sum(row.get('total_tokens') or 0 for row in receipt['telemetry']),
                usage_known=bool(receipt['telemetry']) and all(row.get('usage_reported') for row in receipt['telemetry']))
        except Exception as exc:
            # An interrupted/unknown call is never retried or treated as zero-cost.
            attempt.update(status='unresolved', error_kind=type(exc).__name__, usage_known=False)
            if token_budget is not None:
                # Keep a started reservation on exceptional paths: an unknown
                # call cannot release its budget or authorize another request.
                state['stop_reason'] = 'budget_unresolved_usage'
        write(output / 'progress.json', state)
        if progress:
            progress(dict(attempt))
        if state.get('stop_reason') or attempt['status'] == 'unresolved' or (attempt.get('reason') or '').startswith('local inference request failed:'):
            break
    state.update(status='completed' if not state.get('stop_reason') and len(state['attempts']) == 5 and state['attempts'][-1]['status'] != 'unresolved'
                 and not (state['attempts'][-1].get('reason') or '').startswith('local inference request failed:')
                 else 'stopped', budget_closed=True)
    write(output / 'progress.json', state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--budget-reference', required=True)
    parser.add_argument('--token-budget', help='Shared package reservation ledger; required for v3')
    args = parser.parse_args()
    result = run_suite(args.protocol, args.output, budget_reference=args.budget_reference,
                       token_budget=args.token_budget,
                       progress=lambda row: print(json.dumps(row, ensure_ascii=False), flush=True))
    return 0 if result['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
