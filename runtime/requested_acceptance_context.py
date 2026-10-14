"""Source-backed acceptance examples; declared outcomes are not test results."""
import json

from .narrow_type_evidence_binding import content_digest
from .project_failure_evidence_packet import _test_source
from .project_failure_prompt_context import test_source_groups
from .stage_finalization_workspace import inventory
from .upstream_requested_acceptance import requested_test_bindings


def requested_acceptance_context(project, contract):
    # Advisory requirements may precede an executable native acceptance contract.
    # Keep that route available; prepare_requested_change still gates delivery.
    requirements = contract.get('requirements')
    if (contract.get('constraints') or not isinstance(requirements, list) or not requirements
            or any(not isinstance(row, dict)
                   or not isinstance(row.get('acceptance_examples'), list)
                   or not row['acceptance_examples']
                   or any(not isinstance(e, dict) or e.get('kind') != 'native_test'
                          for e in row['acceptance_examples']) for row in requirements)):
        return {'authority':'no_native_acceptance_evidence', 'status':'not_applicable',
                'contract_digest':contract['contract_digest'],
                'reason':'complete_native_acceptance_not_declared; advisory_only'}
    source = inventory(project)
    bindings = requested_test_bindings(contract, source)
    nodes = list(dict.fromkeys(row['nodeid'] for row in bindings))
    if len(nodes) > 16:
        raise ValueError('requested_acceptance_context_test_limit')
    rows = []
    for node in nodes:
        row = _test_source(project, node)
        if (row is None or row['file_sha256'] != source.get(row['path'])
                or row.get('excerpt_complete') is not True or row.get('support_context') is None):
            raise ValueError('requested_acceptance_source_unavailable')
        rows.append(row)
    result = {'authority': 'source_backed_acceptance; expected_outcomes_are_declared_not_observed',
              'contract_digest': contract['contract_digest'], 'bindings': bindings,
              'test_sources': test_source_groups(rows)}
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > 24000:
        raise ValueError('requested_acceptance_context_byte_limit')
    result['context_digest'] = content_digest(result)
    return result
