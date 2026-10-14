"""Supplemental observations must match source, candidate and artifact bytes."""
import json

import pytest

from runtime.feature_evidence import load_observations
from runtime.feature_workspace import digest


@pytest.mark.parametrize('change', [None, 'source', 'candidate', 'artifact'])
def test_observations_are_bound_to_verified_inputs(tmp_path, change):
    artifact = tmp_path / 'result.json'; artifact.write_bytes(b'{}')
    data = {'schema_version': 'feature_observations.v1',
        'source_hashes': {'engine.py': 'source'}, 'candidate_hashes': {'engine.py': 'patch'},
        'artifacts': [{'path': str(artifact), 'sha256': digest(b'{}')}],
        'observations': {'equal': True}}
    path = tmp_path / 'observations.json'; path.write_text(json.dumps(data))
    expected, candidate = dict(data['source_hashes']), dict(data['candidate_hashes'])
    if change == 'source': expected['engine.py'] = 'changed'
    if change == 'candidate': candidate['engine.py'] = 'changed'
    if change == 'artifact': artifact.write_bytes(b'{"changed":true}')
    if change:
        with pytest.raises(ValueError, match='feature_observation_'):
            load_observations(path, expected, candidate)
    else:
        assert load_observations(path, expected, candidate)['observations'] == {'equal': True}
