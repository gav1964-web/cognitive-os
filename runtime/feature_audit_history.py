"""Persist non-authoritative audit evidence when no fresh audit has run yet."""
import json

from .feature_acceptance import save
from .narrow_type_evidence_binding import content_digest


def history_path(work, binding):
    # Different goals/designs in one invocation must not inherit each other's history.
    return work / ('spec-audit-history-' + content_digest(binding).removeprefix('sha256:') + '.json')


def save_history(work, binding, history):
    if history:
        evidence = {'binding': binding, 'historical_audits': history}
        save(history_path(work, binding), {
            'schema_version': 'feature_audit_history.v1', 'evidence': evidence,
            'digest': content_digest(evidence), 'grants_approval': False})


def load_history(work, binding):
    path = history_path(work, binding)
    if not path.is_file():
        return []
    receipt = json.loads(path.read_text(encoding='utf-8'))
    evidence = receipt.get('evidence', {})
    if (receipt.get('schema_version') != 'feature_audit_history.v1'
            or receipt.get('digest') != content_digest(evidence)
            or evidence.get('binding') != binding
            or not isinstance(evidence.get('historical_audits'), list)):
        raise ValueError('quality_resume_audit_history_integrity')
    return evidence['historical_audits']


def merge_history(*groups):
    merged = []
    for group in groups:
        for row in group:
            if row not in merged:
                merged.append(row)
    return merged
