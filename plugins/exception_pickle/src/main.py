"""Read-only competency contract; patch proposals never apply source changes."""
from __future__ import annotations

from .knowledge import decorate_profile, load_boundary_records, load_exception_pickle_patterns, load_source_contrast_records
from .patch import exception_pickle_reconstruction_patch
from .constructor_samples import _sample_constructor_value
from .source_samples import _constructor_sample_call, _sample_constructor_value_for_source
from .knowledge import validate_patterns_document
from .promotion import prepare_promotion_catalog


def run(payload: dict) -> dict:
    operation = payload['operation']
    if operation == 'prepare_promotion':
        catalog = prepare_promotion_catalog(
            readiness=payload['readiness'], evaluator=payload['evaluator'],
            holdout=payload['holdout'], generated_at=payload['generated_at'],
        )
        return {'status': 'prepared', 'catalog': validate_patterns_document(catalog)}
    if operation == 'validate_patterns':
        return {'status': 'ok', 'catalog': validate_patterns_document(payload['document'])}
    if operation == 'sample_values':
        contracts = payload.get('object_contracts')
        samples = [
            _sample_constructor_value_for_source(
                name, source=payload['source'], class_name=payload['class_name'],
                object_contracts=contracts,
            ) if 'source' in payload else _sample_constructor_value(name, object_contracts=contracts)
            for name in payload['names']
        ]
        return {'status': 'ok', 'samples': samples}
    if operation == 'constructor_call':
        args, kwargs = _constructor_sample_call(
            source=payload['source'], class_name=payload['class_name'],
            required=payload['required'], samples=payload['samples'],
        )
        return {'status': 'ok', 'args': args, 'kwargs': kwargs}
    if operation == 'boundary_profiles':
        return {'status': 'ok', 'records': load_boundary_records()}
    if operation == 'source_contrasts':
        return {'status': 'ok', 'records': load_source_contrast_records()}
    if operation == 'patterns':
        return {'status': 'ok', 'catalog': load_exception_pickle_patterns()}
    if operation == 'decorate_profile':
        profile = decorate_profile(payload['profile'])
        return {'status': 'ok', 'profile': profile}
    if operation == 'propose_patch':
        result = exception_pickle_reconstruction_patch(
            payload['source'], class_name=payload['class_name'], recipe=payload['recipe'],
            constructor_name=payload.get('constructor_name', '__init__'),
        )
        return {'status': 'proposed' if result else 'not_applicable', 'patch': result}
    raise ValueError('unsupported_competency_operation')
