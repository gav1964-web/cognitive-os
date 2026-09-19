"""Keep draft and edited final assertions distinct throughout review handoffs."""
from .competency_knowledge import ROOT
from .description_shape import report_draft, checked_report_description
from .project_description_review import draft_claims


def report_claims(report, namespace, *, root=ROOT):
    if namespace not in ('draft', 'final'):
        raise ValueError('claim_review_invalid_namespace')
    if namespace == 'final':
        if report.get('status') != 'described':
            raise ValueError('claim_review_final_description_required')
        description = checked_report_description(report, root=root)
    else:
        description = report_draft(report, root=root)
    return draft_claims(description)
