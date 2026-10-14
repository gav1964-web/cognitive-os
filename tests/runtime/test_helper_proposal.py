"""Proposal envelope denies forged coordinator identity before source writes."""
import pytest

from runtime.helper_proposal import validate_helper_proposal, legacy_helper_proposal, RESERVED_OPERATION_FIELDS


def _proposal():
    return {'schema_version':'helper_proposal.v1','status':'proposed','source':'pass\n',
            'operation_details':{'custom':{'count':1}},'reason':None}


def test_result_is_detached_and_legacy_refusal_is_exact():
    original = _proposal()
    result = validate_helper_proposal(original)
    result['operation_details']['custom']['count'] = 2
    assert original['operation_details']['custom']['count'] == 1
    assert legacy_helper_proposal(None, fields=('unused',), reason='pattern_not_proven') == {
        'schema_version':'helper_proposal.v1','status':'not_applicable','source':None,
        'operation_details':{},'reason':'pattern_not_proven'}


@pytest.mark.parametrize('field', sorted(RESERVED_OPERATION_FIELDS))
def test_proposal_cannot_override_coordinator(field):
    proposal = _proposal()
    proposal['operation_details'][field] = 'forged'
    with pytest.raises(ValueError, match='overrides_coordinator'):
        validate_helper_proposal(proposal)


@pytest.mark.parametrize('changes', [
    {'schema_version':'unknown'}, {'status':'applied'}, {'source':None}, {'reason':'authorized'},
    {'source_apply':True}, {'operation_details':[]}, {'status':'not_applicable'},
])
def test_malformed_or_authority_bearing_envelope_rejected(changes):
    with pytest.raises(ValueError):
        validate_helper_proposal({**_proposal(), **changes})
