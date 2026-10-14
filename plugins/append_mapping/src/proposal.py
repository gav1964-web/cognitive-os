"""Owned append-mapping result metadata; no execution or application authority."""


def helper_proposal(patch: dict | None) -> dict:
    return {
        'schema_version': 'helper_proposal.v1',
        'status': 'proposed' if patch is not None else 'not_applicable',
        'source': patch['source'] if patch is not None else None,
        'operation_details': {
            key: patch[key] for key in (
                'loop_variable', 'accumulator', 'mapping_field_count', 'mapping_source',
            )
        } if patch is not None else {},
        'reason': None if patch is not None else 'append_mapping_helper_pattern_not_proven',
    }
