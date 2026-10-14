"""Experimental v1 scheduling; skipped audits are never semantic approvals."""

MODES = ('always', 'on_feedback')


def audit_decision(mode, *, feedback=False, scope=(), retained_campaign=False):
    if mode not in MODES:
        raise ValueError('quality_unknown_audit_mode')
    reasons = []
    if mode == 'always':
        reasons.append('default_full_audit')
    if feedback:
        reasons.append('observed_admission_or_execution_feedback')
    if len(scope) > 1:
        reasons.append('multiple_production_paths')
    if retained_campaign:
        reasons.append('retained_counterexamples')
    return {'contract': 'development_quality.audit_schedule.v1', 'mode': mode,
            'required': bool(reasons), 'reasons': reasons,
            'grants_approval': False, 'experimental': mode != 'always'}
