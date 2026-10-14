"""Citation authority admission, not an automatic semantic contradiction detector."""
from pathlib import PurePosixPath


def claim_grounding(description, evidence):
    sources = {s['id']: s for s in evidence['sources']}
    claims = [('purpose', description['purpose'])]
    claims += [(f'{key}.{i}', row) for key in ('scenarios', 'data_flow')
               for i, row in enumerate(description[key])]
    rows = []
    for claim_id, claim in claims:
        implementation, documentation, other = [], [], []
        for ref in claim['evidence_ids']:
            source = sources[ref]
            path = PurePosixPath(source['path'].replace('\\', '/').lower())
            if source.get('authority') == 'documentation_claims' or path.name.startswith('readme'):
                documentation.append(ref)
            elif (path.suffix in {'.py', '.js', '.ts', '.tsx', '.html', '.sh', '.bat'}
                  and not any(p in {'tests', 'test', 'docs', 'examples'} for p in path.parts)
                  and not path.name.startswith('test_')):
                implementation.append(ref)
            else:
                other.append(ref)
        rows.append({'claim_id': claim_id, 'implementation_evidence_ids': implementation,
                     'documentation_evidence_ids': documentation, 'other_evidence_ids': other,
                     'status': 'implementation_cited' if implementation else
                               'documentation_only' if documentation and not other else 'implementation_not_cited'})
    return {'schema_version': 'description_grounding.v1', 'claims': rows,
            'semantic_verified': False, 'conflicts_automatically_detected': False}
