"""Plugin-owned shape adaptation with replayable provenance, before strict validation."""
from .competency_knowledge import ROOT, invoke_knowledge


def normalize_description(raw, evidence, *, root=ROOT):
    from .project_description import _validate_description
    result = invoke_knowledge('project_description', {
        'project_root': evidence['root'], 'action': 'normalize',
        'description_result': raw, 'evidence': evidence}, root=root)
    normalized = _validate_description(result['normalized_description'],
                                      {row['id'] for row in evidence['sources']})
    return normalized, result['shape_receipt']


def report_draft(report, *, root=ROOT):
    """Old reports remain strict; new receipts must rederive exactly from raw JSON."""
    from .project_description import _validate_description
    if 'shape_normalization' not in report:
        return _validate_description(report['raw_response'],
                                     {row['id'] for row in report['evidence']['sources']})
    records = report['shape_normalization']
    if not isinstance(records, dict) or 'draft' not in records or set(records) - {'draft', 'review'}:
        raise ValueError('description_shape_receipt_mismatch')
    receipt = records['draft']
    draft, expected = normalize_description(report['raw_response'], report['evidence'], root=root)
    if receipt != expected:
        raise ValueError('description_shape_receipt_mismatch')
    return draft


def checked_report_description(report, *, root=ROOT):
    """A normalized review cannot silently replace the raw model response downstream."""
    from .project_description import _validate_description
    description = _validate_description(report['description'],
                                        {row['id'] for row in report['evidence']['sources']})
    if 'shape_normalization' in report:
        report_draft(report, root=root)
        reviewed = report.get('review_response')
        if not isinstance(reviewed, dict) or 'description' not in reviewed:
            raise ValueError('description_shape_missing_review')
        normalized, receipt = normalize_description(reviewed['description'], report['evidence'], root=root)
        if receipt != report['shape_normalization'].get('review') or normalized != description:
            raise ValueError('description_shape_receipt_mismatch')
    return description
