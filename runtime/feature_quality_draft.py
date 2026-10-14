"""Preserve unaccepted complete proposals when a correction omits earlier files."""
import json
from hashlib import sha256


def frozen_test_mismatches(frozen, submitted):
    """Explain exact immutable-test drift without replacing model-authored bytes."""
    differences = []
    for test in frozen:
        expected, actual = test['content'], submitted.get(test['path'])
        if actual == expected:
            continue
        row = {'path': test['path'],
               'expected_sha256': sha256(expected.encode('utf-8')).hexdigest(),
               'actual_sha256': None,
               'instruction': 'Return the complete immutable_previous_tests content for this path exactly; do not repair or regenerate it.'}
        if isinstance(actual, str):
            offset = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b),
                          min(len(expected), len(actual)))
            start = max(0, offset - 80)
            row.update(actual_sha256=sha256(actual.encode('utf-8')).hexdigest(),
                       first_difference_offset=offset, context_start=start,
                       expected_context=expected[start:offset + 81],
                       actual_context=actual[start:offset + 81])
        else:
            row['reason'] = 'Missing path or non-string content'
        differences.append(row)
    return differences


def draft_binding(payload, role):
    dependency = 'architect' if role == 'spec_writer' else 'analyzer'
    return json.dumps({'goal': payload.get('goal'),
                       'dependency': payload.get('artifacts', {}).get(dependency),
                       'source_inventory_digest': payload.get('source_inventory_digest')}, sort_keys=True)


def missing_draft_files(previous, value):
    def paths(artifact):
        tests = artifact.get('tests', [])
        return {t['path'] for t in tests if isinstance(t, dict) and isinstance(t.get('path'), str)} if isinstance(tests, list) else set()
    old, new = paths(previous), paths(value)
    return sorted(old - new)


def audit_policy_matches(instruction, policy):
    """Legacy receipts include the policy plus an optional lossless-ref suffix."""
    expected = 'Return one JSON object only.\n' + policy
    return instruction == expected or instruction.startswith(
        expected + '\nInput tests with content_reference ')


def historical_audit(audit, payload):
    """Keep a superseded rejection as evidence, without authorizing its demands."""
    previous = payload.get('previous_unaccepted_draft') or {}
    return {'request_digest': audit['request_digest'],
            'instruction_sha256': sha256(audit['messages'][0]['content'].encode()).hexdigest(),
            'audit': audit['raw_response'],
            'prior_audit_issues': payload.get('prior_audit_issues', []),
            'previous_issues': previous.get('issues', []),
            'prior_issues': previous.get('prior_issues', []),
            'authority': 'historical_only_requires_current_audit'}


def correction_feedback(value, issues, previous=None):
    feedback = {'rejected': value, 'issues': issues,
                'instruction': 'Correct only these contract/design defects. Preserve verified facts. '
                'Return the COMPLETE proposal preserving required coverage. Unaccepted files may '
                'be reorganized; the fresh auditor receives the previous draft for comparison. Drafts are '
                'not accepted, frozen, or present on disk; fresh audit and native checks are required.'}
    audit_issues = list((previous or {}).get('prior_audit_issues', []))
    for issue in issues:
        if isinstance(issue, dict):
            audit = issue.get('acceptance_audit', {})
            if isinstance(audit, dict) and isinstance(audit.get('issues'), list):
                for item in audit['issues']:
                    if item not in audit_issues:
                        audit_issues.append(item)
    if audit_issues:
        feedback['prior_audit_issues'] = audit_issues
    if previous and previous.get('historical_audits'):
        feedback['historical_audits'] = previous['historical_audits']
    lost_cases = any(isinstance(issue, dict) and issue.get('draft_case_continuity', {}).get('unexplained')
                     for issue in issues)
    if previous and (missing_draft_files(previous['rejected'], value) or lost_cases):
        feedback.update(rejected=previous['rejected'], incomplete_correction=value,
                        prior_issues=previous.get('prior_issues', previous['issues']))
    return feedback
