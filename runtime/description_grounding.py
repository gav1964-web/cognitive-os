"""Recompute plugin-owned citation authority at the acceptance boundary."""
from .competency_knowledge import ROOT, invoke_knowledge


def description_grounding(description, evidence, *, root=ROOT):
    from .project_description import _validate_description
    _validate_description(description, {s['id'] for s in evidence['sources']})
    # Legacy acceptance packets may retain only source identity, not excerpts.
    evidence = {**evidence, 'sources': [{**s, 'excerpt': s.get('excerpt', '')} for s in evidence['sources']]}
    return invoke_knowledge('project_description', {
        'action': 'grounding', 'project_root': evidence['root'], 'evidence': evidence,
        'description_result': description}, root=root)['claim_grounding']
