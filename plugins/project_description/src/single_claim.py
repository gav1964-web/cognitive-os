"""Single-claim review contract; quote validation does not certify semantics."""
from .claim_evidence import review_context


def prepare(evidence, claims, policy):
    if len(claims) != 1:
        raise ValueError('single_claim_required')
    return review_context(evidence, claims, policy)


def validate_result(response, evidence):
    if not isinstance(response, dict) or set(response) != {'verdict', 'reason', 'citations', 'proposed_text'}:
        raise ValueError('claim_review_invalid_result')
    if (response['verdict'] not in ('supported', 'refuted', 'uncertain')
            or not isinstance(response['reason'], str) or not response['reason'].strip()
            or len(response['reason']) > 2000
            or (response['proposed_text'] is not None and (
                not isinstance(response['proposed_text'], str) or not response['proposed_text'].strip()
                or len(response['proposed_text']) > 2000))):
        raise ValueError('claim_review_invalid_verdict')
    citations = response['citations']
    if (not isinstance(citations, list) or len(citations) > 6
            or (response['verdict'] != 'uncertain' and not citations)):
        raise ValueError('claim_review_citations_required')
    sources = {row['id']: row for row in evidence['sources']}
    for citation in citations:
        if (not isinstance(citation, dict) or set(citation) != {'source_id', 'quote'}
                or not isinstance(citation['source_id'], str) or citation['source_id'] not in sources
                or not isinstance(citation['quote'], str) or not 8 <= len(citation['quote']) <= 1000
                or not citation['quote'].strip()
                or citation['quote'] not in sources[citation['source_id']]['excerpt']):
            raise ValueError('claim_review_quote_not_in_visible_source')
    return {'quote_validation': 'passed', 'semantic_verified': False, 'execution_authorized': False}
