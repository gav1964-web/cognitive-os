"""Lossless v1 envelope repair; never infer text, citations or semantic truth."""
from copy import deepcopy
import hashlib
import json


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def normalize(value, policy):
    if policy != {'schema_version': 'description_shape_policy.v1',
                  'singleton_claim_arrays': ['scenarios', 'data_flow']}:
        raise ValueError('description_shape_unsupported_policy')
    result = deepcopy(value)
    operations = []
    if isinstance(result, dict):
        for key in policy['singleton_claim_arrays']:
            claim = result.get(key)
            if (isinstance(claim, dict) and set(claim) == {'text', 'evidence_ids'}
                    and isinstance(claim['text'], str) and claim['text'].strip()
                    and isinstance(claim['evidence_ids'], list) and claim['evidence_ids']
                    and all(isinstance(ref, str) for ref in claim['evidence_ids'])):
                result[key] = [claim]
                operations.append({'path': '/' + key, 'operation': 'wrap_single_claim'})
    return result, {'schema_version': 'description_shape.v1', 'operations': operations,
                    'raw_sha256': _digest(value), 'normalized_sha256': _digest(result),
                    'semantic_verified': False}
