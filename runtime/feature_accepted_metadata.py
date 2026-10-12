"""Reuse qualified per-test metadata without granting new acceptance authority."""
from copy import deepcopy

from .feature_quality_draft import draft_binding
from .narrow_type_evidence_binding import content_digest
from plugins.development_quality.src.main import run as quality_contract


def capture(specification, *, goal, design, source_hashes):
    if source_hashes is None or not specification.get('baseline_expectations'):
        return None
    return {'binding': draft_binding({'goal': goal, 'artifacts': {'architect': design},
                'source_inventory_digest': content_digest(source_hashes)}, 'spec_writer'),
            'tests': deepcopy(specification['tests']),
            'baseline_expectations': deepcopy(specification['baseline_expectations']),
            'case_plan': deepcopy(specification.get('case_plan', []))}


def restore(value, accepted, binding, *, allow_label_correction=False):
    """Copy only known rows for byte-identical tests under the original binding.

    Unknown/duplicate predictions and changed/missing tests remain subject to
    ordinary admission. Every merged prediction is natively checked again, since
    new fixtures/imports can change execution even when an old test is unchanged.
    """
    if not accepted or accepted['binding'] != binding:
        return value, []
    tests = value.get('tests', [])
    if not isinstance(tests, list) or any(not isinstance(t, dict) for t in tests):
        return value, []
    result, changes = deepcopy(value), []
    for field in ('baseline_expectations', 'case_plan'):
        if not accepted.get(field):
            continue
        rows = result.get(field, [])
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            continue
        for prediction in accepted[field]:
            node = prediction['node']
            path = node.partition('::')[0]
            known = [t for t in accepted['tests'] if t.get('path') == path]
            incoming = [t for t in tests if t.get('path') == path]
            if (len(known) != 1 or len(incoming) != 1
                    or incoming[0].get('content') != known[0]['content']
                    or sum(r.get('node') == node for r in accepted[field]) != 1):
                continue
            matches = [i for i, row in enumerate(rows) if row.get('node') == node]
            if len(matches) > 1:
                continue  # Never hide ambiguous model output.
            old = rows[matches[0]] if matches else None
            if (field == 'case_plan' and allow_label_correction and old is not None
                    and quality_contract({'action': 'allow_qualified_label_correction',
                        'previous': prediction, 'current': old, 'artifact': accepted})['allowed']):
                changes.append({'field': field, 'node': node, 'previous': deepcopy(prediction),
                    'model_correction': deepcopy(old), 'test_digest': content_digest(known[0]),
                    'grants_approval': False})
                continue
            if old == prediction:
                continue
            if matches:
                rows[matches[0]] = deepcopy(prediction)
            else:
                rows.append(deepcopy(prediction))
            result[field] = rows
            changes.append({'field': field, 'node': node, 'previous': old, 'restored': deepcopy(prediction),
                            'test_digest': content_digest(known[0]), 'grants_approval': False})
    return result, changes
