"""Derive one missing policy label from a complete runtime-owned inventory.

This never authors tests, resolves semantic contradictions or grants admission.
An explicit value, even null or invalid, is left for the ordinary validator.
"""
from copy import deepcopy
from pathlib import PurePosixPath


def allow_qualified_label_correction(previous, current, accepted):
    """Admit a model-authored correction of a legacy cross-axis label only."""
    if (not isinstance(current, dict) or previous.get('kind') not in {'feature_gap', 'feature_control'}
            or current.get('kind') not in {'feature', 'boundary'}
            or {k: v for k, v in previous.items() if k != 'kind'}
            != {k: v for k, v in current.items() if k != 'kind'}):
        return False
    from .baseline_expectations import classification
    rows = [r for r in accepted.get('baseline_expectations', [])
            if isinstance(r, dict) and r.get('node') == previous.get('node')]
    return len(rows) == 1 and classification(rows[0]) == previous['kind']


def repair_metadata(artifact, source_paths):
    result = deepcopy(artifact)
    changes = []
    known = (isinstance(source_paths, list) and bool(source_paths)
             and all(isinstance(p, str) and p for p in source_paths))
    has_suite = known and any(
        PurePosixPath(p).name.startswith('test_') or
        PurePosixPath(p).name.endswith('_test.py') or
        PurePosixPath(p).name == 'test.py' for p in source_paths if p.endswith('.py'))
    plan = artifact.get('case_plan')
    preservation = isinstance(plan, list) and any(
        isinstance(row, dict) and row.get('kind') == 'preservation' for row in plan)
    if (known and not has_suite and artifact.get('status') == 'ready'
            and artifact.get('regression_tests') == [] and preservation
            and 'regression_policy' not in artifact):
        result['regression_policy'] = 'new_preservation_only'
        changes.append({'field': 'regression_policy', 'before': 'absent',
                        'after': 'new_preservation_only',
                        'basis': 'complete_inventory_has_no_existing_test_suite'})
    return {'artifact': result, 'changes': changes, 'grants_approval': False}
