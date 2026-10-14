"""Source-bound observations of external verification artifacts for role review."""
import json
from pathlib import Path

from .feature_workspace import digest


def load_observations(path, expected, candidate_hashes):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if (data.get('schema_version') != 'feature_observations.v1'
            or data.get('source_hashes') != expected
            or data.get('candidate_hashes') != candidate_hashes):
        raise ValueError('feature_observation_identity_mismatch')
    artifacts = data.get('artifacts', [])
    if not 1 <= len(artifacts) <= 20:
        raise ValueError('feature_observation_artifacts_required')
    for artifact in artifacts:
        if digest(Path(artifact['path']).read_bytes()) != artifact['sha256']:
            raise ValueError('feature_observation_artifact_changed')
    summary = data['observations']
    if not isinstance(summary, dict) or len(json.dumps(summary).encode()) > 16000:
        raise ValueError('feature_observation_summary_limit')
    return {'observations': summary, 'note': 'Observed artifact comparison, not a replacement for frozen acceptance or reviewer judgment.'}
