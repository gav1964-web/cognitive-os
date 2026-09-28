"""Resume completed roles against the same goal, project and source snapshot."""
import json
from pathlib import Path

from .feature_prompts import COMMON, ROLE
from .feature_workspace import read_sources, merge_reads, digest
from .narrow_type_evidence_binding import content_digest


def candidate_matches(previous, current, tests, *, allow_test_extension=False):
    """Only newly qualified test files may extend an unchanged candidate."""
    if not allow_test_extension:
        return previous == current
    return (all(current.get(name) == value for name, value in previous.items())
            and all(name in tests and value == digest(tests[name])
                    for name, value in current.items() if name not in previous))


def latest_read_paths(prior):
    transcript = Path(prior).parent / 'transcript.json'
    if not transcript.is_file():
        return set()
    calls = json.loads(transcript.read_text(encoding='utf-8'))
    if not calls:
        return set()
    response = calls[-1].get('raw_response', {})
    return {row['path'] for row in response.get('reads', [])} if response.get('status') == 'read' else set()


def _replay_read_request(project, expected, requests, errors=None):
    from .feature_context_reads import read_request
    rows, missing = read_request(project, expected, requests)
    if errors is not None:
        errors.extend(missing)
    return rows


def recover_pending_read(prior, project, expected, role=None, *, errors=None):
    from .feature_read_response import recover_read
    path = Path(prior).parent / 'transcript.json'
    if not path.is_file():
        return []
    calls = json.loads(path.read_text(encoding='utf-8'))
    last = calls[-1] if calls else {}
    if role and not any(e.get('provider_label') == 'feature:' + role for e in last.get('telemetry', [])):
        return []
    request = last.get('raw_response') if last.get('status') == 'returned' else recover_read(last)
    if not isinstance(request, dict) or request.get('status') != 'read':
        return []
    return _replay_read_request(project, expected, request['reads'], errors)


def load_roles(prior, project, expected, goal, *, transcript_context=True):
    prior = Path(prior)
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    source = json.loads((prior / 'source-inventory.json').read_text(encoding='utf-8'))
    if (source != expected or report['goal'] != goal
            or Path(report['project']).resolve() != project):
        raise ValueError('feature_checkpoint_identity_changed')
    artifacts = {}
    for role in ('analyzer', 'architect'):
        value = json.loads((prior / (role + '.json')).read_text(encoding='utf-8'))
        if value != report['artifacts'].get(role) or value.get('status') != 'ready':
            raise ValueError('feature_checkpoint_role_mismatch')
        artifacts[role] = value
    # Retain the exact source ranges the pending role already requested, instead
    # of paying for another discovery round. Re-read bytes from the current tree.
    transcript = prior.parent / 'transcript.json'
    rows = []
    selections = prior / 'spec-source-ranges.json'
    if selections.is_file():
        for selected in json.loads(selections.read_text(encoding='utf-8')):
            rows.extend(read_sources(project, expected, [selected], max_bytes=65000))
    if transcript.is_file():
        calls = json.loads(transcript.read_text(encoding='utf-8'))
        for call in reversed(calls):
            messages = call.get('messages', [])
            spec_role = (len(messages) == 2 and (messages[0].get('content') == COMMON + ROLE['spec_writer']
                or (messages[0].get('content', '').startswith(COMMON)
                    and any(e.get('provider_label') == 'feature:spec_writer' for e in call.get('telemetry', [])))))
            if spec_role:
                payload = json.loads(messages[1]['content'])
                if payload['goal'] != goal:
                    raise ValueError('feature_checkpoint_pending_goal_changed')
                if transcript_context:
                    for row in payload['sources']:
                        rows.extend(read_sources(project, expected, [row], max_bytes=65000))
                response = call.get('raw_response', {})
                if call.get('status') == 'returned' and response.get('status') == 'read':
                    rows.extend(read_sources(project, expected, response['reads']))
                break
    return artifacts, merge_reads([], rows)


def pending_spec(prior):
    """Recheck an unchanged rejected proposal before paying to regenerate it."""
    prior = Path(prior)
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    attempts = report.get('spec_attempts', [])
    if not attempts or attempts[-1].get('status') != 'rejected':
        return None
    value = attempts[-1]['feedback']['rejected_spec']
    saved = json.loads((prior / f'spec-proposal-{len(attempts)}.json').read_text(encoding='utf-8'))
    if value != saved:
        raise ValueError('feature_checkpoint_spec_mismatch')
    return saved


def previous_native_feedback(prior):
    report = json.loads((Path(prior) / 'report.json').read_text(encoding='utf-8'))
    for attempt in reversed(report.get('spec_attempts', [])):
        feedback = attempt.get('feedback', {})
        if feedback.get('baseline'):
            return {'specification_digest': content_digest(feedback['rejected_spec']),
                    'baseline': feedback['baseline']}
        if feedback.get('previous_native_attempt'):
            return feedback['previous_native_attempt']
    return None


def qualified_spec(prior):
    prior = Path(prior)
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    value = report.get('artifacts', {}).get('spec_writer')
    if value is None:
        return None
    saved = json.loads((prior / 'spec_writer.json').read_text(encoding='utf-8'))
    hashes = {row['path']: digest(row['content'].encode('utf-8')) for row in value['tests']}
    if value != saved or hashes != report.get('frozen_test_hashes'):
        raise ValueError('feature_checkpoint_frozen_spec_mismatch')
    ordinal = len(report['spec_attempts'])
    raw = json.loads((prior / f'spec-proposal-{ordinal}.json').read_text(encoding='utf-8'))
    return {'raw': raw, 'accepted': value, 'format': report.get('spec_format', 'python')}


def verified_candidate(prior, *, require_passed=True):
    """Load a previously passing proposal; callers must reexecute and match hashes."""
    prior = Path(prior)
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    attempts = report.get('attempts', [])
    if not attempts or attempts[-1].get('passed') is not require_passed:
        raise ValueError('feature_resume_requires_verified_candidate')
    ordinal = len(attempts)
    saved = json.loads((prior / f'attempt-{ordinal}/verification.json').read_text(encoding='utf-8'))
    if saved != attempts[-1]:
        raise ValueError('feature_candidate_receipt_mismatch')
    proposal = json.loads((prior / f'proposal-{ordinal}.json').read_text(encoding='utf-8'))
    return {'proposal': proposal, 'candidate_hashes': saved['candidate_hashes'],
            'previous_error': report.get('reason')}


def rejected_candidate(prior):
    """Return the last rejected proposal for fresh native feedback, not approval."""
    if prior is None:
        return None
    prior = Path(prior)
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    attempts = report.get('attempts', [])
    if not attempts:
        return None
    if attempts[-1].get('passed') is True:
        review = report.get('artifacts', {}).get('reviewer', {})
        if review.get('status') != 'ready' or review.get('decision') != 'reject':
            return None
        if json.loads((prior / 'reviewer.json').read_text(encoding='utf-8')) != review:
            raise ValueError('feature_rejected_review_receipt_mismatch')
        return {**verified_candidate(prior), 'review': review}
    if attempts[-1].get('passed') is not False:
        return None
    return verified_candidate(prior, require_passed=False)


def review_draft(prior, proposal, spec):
    """An unaccepted draft may carry reasoning forward, never grant approval."""
    calls = json.loads((Path(prior).parent / 'transcript.json').read_text(encoding='utf-8'))
    last = calls[-1]
    payload = json.loads(last['messages'][1]['content'])
    events = last.get('telemetry', [])
    evidence = last.get('response_evidence', [])
    if (last.get('status') != 'failed' or not last.get('usage_known')
            or not events or any(e.get('provider_label') != 'feature:reviewer' for e in events)
            or payload.get('proposal') != proposal
            or payload.get('artifacts', {}).get('spec_writer', {}).get('tests') != spec['tests']
            or len(evidence) != 1 or not isinstance(evidence[0].get('content'), str)
            or not 1 <= len(evidence[0]['content'].encode()) <= 16000):
        raise ValueError('feature_review_draft_not_bound')
    return {'content': evidence[0]['content'], 'accepted': False,
        'instruction': 'Prior same-candidate draft failed JSON validation and grants NO approval. Review the full patch/tests, cited sources and observations; return a fresh complete decision or request needed source.',
        'previously_supplied_ranges': [{k: r[k] for k in ('path', 'start', 'end')}
                                      for r in payload['sources']]}


def review_reads(prior, project, expected, role='reviewer', *, errors=None):
    """Retain accepted consumer read requests after a role is interrupted."""
    prior = Path(prior)
    selections = prior / (role + '-source-ranges.json')
    requested = json.loads(selections.read_text(encoding='utf-8')) if selections.is_file() else []
    transcript = prior.parent / 'transcript.json'
    rows = []
    for item in requested:
        rows.extend(read_sources(project, expected, [item], max_bytes=65000))
    if transcript.is_file():
        for call in json.loads(transcript.read_text(encoding='utf-8')):
            response = call.get('raw_response', {})
            if (call.get('status') == 'returned' and response.get('status') == 'read'
                    and any(e.get('provider_label') == 'feature:' + role for e in call.get('telemetry', []))):
                rows.extend(_replay_read_request(project, expected, response['reads'], errors))
    return merge_reads([], rows)


def observed_regressions(prior, expected):
    """Offer files whose observed tests passed; acceptance reruns the whole file."""
    prior = Path(prior)
    saved = json.loads((prior / 'source-inventory.json').read_text(encoding='utf-8'))
    if saved != expected:
        raise ValueError('feature_regression_observation_stale')
    modules = {p: p[:-3].replace('/', '.') for p in expected
               if p.endswith('.py') and Path(p).name.startswith('test_')}
    for folder in ('acceptance-3', 'acceptance-2', 'acceptance'):
        receipt = prior / folder / 'baseline.json'
        if not receipt.is_file():
            continue
        regression = json.loads(receipt.read_text(encoding='utf-8'))['regression']
        if not regression['source_unchanged']:
            continue
        grouped = {}
        for test, status in regression['tests'].items():
            owner = test.partition('::')[0]
            matches = [p for p, m in modules.items() if owner == m or owner.startswith(m + '.')]
            if len(matches) == 1:
                grouped.setdefault(matches[0], []).append(status)
        passed = sorted(p for p, states in grouped.items() if states and set(states) == {'passed'})
        if passed:
            return {'files': passed, 'receipt': str(receipt.resolve()),
                    'scope': 'all observed tests passed; proposed whole files must be rerun, unobserved tests are not certified'}
    return {'files': []}
