"""Check exact absence assertions, without approving product semantics."""
from .claim_evidence import literal_matches, quoted_terms


def audit_review(evidence, claims, reviews, *, visible_evidence=None):
    originals = {row['id']: row for row in claims}
    if (len(reviews) != len(originals)
            or {row.get('claim_id') for row in reviews} != set(originals)):
        raise ValueError('description_incomplete_claim_review')
    sources = {row['id']: row for row in evidence['sources']}
    visible = sources if visible_evidence is None else {row['id']: row for row in visible_evidence['sources']}
    for ref, row in visible.items():
        if ref not in sources or any(row[key] != sources[ref][key] for key in ('path', 'sha256')):
            raise ValueError('description_audit_visible_source_mismatch')
    findings = []
    for review in reviews:
        claim = originals.get(review.get('claim_id'))
        if claim is None:
            raise ValueError('description_audit_unknown_claim')
        checks = review.get('checks', [])
        if not isinstance(checks, list) or len(checks) > 8:
            raise ValueError('description_invalid_literal_checks')
        for check in checks:
            if (not isinstance(check, dict) or set(check) != {'kind', 'value', 'evidence_ids'}
                    or check['kind'] != 'literal_absent' or not isinstance(check['value'], str)
                    or not 2 <= len(check['value']) <= 96 or not check['value'].strip()
                    or not isinstance(check['evidence_ids'], list) or not check['evidence_ids']
                    or any(not isinstance(ref, str) or ref not in visible for ref in check['evidence_ids'])):
                raise ValueError('description_invalid_literal_checks')
            matches = literal_matches(check['value'], [visible[ref] for ref in check['evidence_ids']])
            if matches:
                findings.append({'claim_id': claim['id'], 'kind': 'contradicted_literal_absence',
                                 'matches': matches, 'scope': 'review_input_excerpts',
                                 'semantic_status': 'unverified'})
        if review['action'] != 'removed':
            continue
        terms = quoted_terms(review['reason'])
        matches = [hit for term in terms for hit in literal_matches(term, evidence['sources'], limit=1)][:6]
        # Legacy prose cannot be interpreted reliably. Surface overlap, not a fabricated verdict.
        findings.append({'claim_id': claim['id'],
                         'kind': 'removal_mentions_present_literals' if matches else 'removal_requires_review',
                         'matches': matches, 'scope': 'full_saved_excerpts', 'semantic_status': 'unverified'})
    return {'schema_version': 'description_review_audit.v1', 'findings': findings,
            'status': 'needs_review' if findings else 'no_mechanical_findings',
            'semantic_verified': False, 'automatic_claim_restoration': False}
