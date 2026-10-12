"""Stop repeat candidates before reexecution; text changes are not code progress."""
from .feature_workspace import digest
from .narrow_type_evidence_binding import content_digest


def repeated_candidate(attempts, tests, edits):
    hashes = {n: digest(b) for n, b in {**tests, **edits}.items()}
    for previous in attempts:
        if previous.get('passed') is False and previous.get('candidate_hashes') == hashes:
            return {'candidate_hashes': hashes, 'previous_junit': previous.get('junit'),
                    'failure_fingerprint': content_digest(previous.get('tests', {})),
                    'inference_or_test_approval': False}
    return None


def conflicting_failures(result):
    """Disjoint assertion failures suggest a dispute; this grants no revision."""
    if result.get('reason') != 'feature_acceptance_failed':
        return False
    attempts = result.get('attempts', [])
    if len(attempts) != 2 or any(a.get('passed') or a.get('counts', {}).get('error') for a in attempts):
        return False
    left, right = (set(a.get('assertion_failures', [])) for a in attempts)
    return bool(left and right and left.isdisjoint(right))
