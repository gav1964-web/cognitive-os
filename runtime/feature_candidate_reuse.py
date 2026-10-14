"""Reexecute a prior reviewed COS patch against an extended qualified suite."""
import json
from pathlib import Path

from .feature_checkpoint import load_roles, qualified_spec, verified_candidate


def load_candidate(checkpoint, *, project, expected, goal, design, specification):
    checkpoint = Path(checkpoint).resolve()
    roles, _ = load_roles(checkpoint, project, expected, goal)
    report = json.loads((checkpoint / 'report.json').read_text(encoding='utf-8'))
    review = report.get('artifacts', {}).get('reviewer', {})
    if (roles['architect'] != design or report.get('status') != 'verified'
            or review.get('decision') != 'approve'
            or json.loads((checkpoint / 'reviewer.json').read_text(encoding='utf-8')) != review):
        raise ValueError('feature_prior_candidate_requires_same_design_and_review')
    old = qualified_spec(checkpoint)
    current = {t['path']: t['content'] for t in specification['tests']}
    if (not old or any(current.get(t['path']) != t['content'] for t in old['accepted']['tests'])
            or not set(old['accepted'].get('regression_tests', []))
            .issubset(specification.get('regression_tests', []))):
        raise ValueError('feature_prior_candidate_requires_test_extension')
    # The saved proposal is not installed here. The normal materializer and native
    # runner must reproduce its production hashes before a fresh Reviewer call.
    return verified_candidate(checkpoint)
