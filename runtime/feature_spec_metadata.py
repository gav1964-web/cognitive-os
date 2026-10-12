"""Journal deterministic plugin-owned metadata repair before normal admission."""
from plugins.development_quality.src.main import run as quality_contract
from .feature_acceptance import save
from .narrow_type_evidence_binding import content_digest


def repair_spec_metadata(value, expected, receipt):
    result = quality_contract({'action': 'repair_metadata', 'artifact': value,
                               'source_paths': sorted(expected) if expected else None})
    if result['changes']:
        save(receipt, {'schema_version': 'feature_spec_metadata.v1',
             'original': value, 'normalized': result['artifact'],
             'original_digest': content_digest(value),
             'normalized_digest': content_digest(result['artifact']),
             'source_inventory_digest': content_digest(expected),
             'changes': result['changes'], 'grants_approval': False})
    return result['artifact'], result['changes']
