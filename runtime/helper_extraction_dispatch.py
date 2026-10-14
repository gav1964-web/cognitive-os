"""Bounded dispatch to registered helper competencies; coordination stays outside."""
from .append_mapping_contract import propose_append_mapping_result
from .json_serialization_contract import propose_json_serialization_result
from .json_parsing_contract import propose_json_parsing_result
from .helper_proposal import validate_helper_proposal
from .text_splitting_contract import propose_text_splitting_result


def _append(source, *, origin_symbol, proposed_symbol, recipe):
    return propose_append_mapping_result(
        source, origin_symbol=origin_symbol, proposed_symbol=proposed_symbol,
        maximum_mapping_fields=int(recipe.get('maximum_mapping_fields') or 12),
    )


def _json_dumps(source, *, origin_symbol, proposed_symbol, recipe):
    return propose_json_serialization_result(
        source, origin_symbol=origin_symbol, proposed_symbol=proposed_symbol,
        maximum_free_variables=int(recipe.get('maximum_free_variables') or 1),
    )


def _json_loads(source, *, origin_symbol, proposed_symbol, recipe):
    return propose_json_parsing_result(source, origin_symbol=origin_symbol, proposed_symbol=proposed_symbol)


def _splitlines(source, *, origin_symbol, proposed_symbol, recipe):
    return propose_text_splitting_result(source, origin_symbol=origin_symbol, proposed_symbol=proposed_symbol)


_HANDLERS = {
    'extract_append_mapping_helper': _append,
    'extract_json_dumps_helper': _json_dumps,
    'extract_json_loads_helper': _json_loads,
    'extract_splitlines_helper': _splitlines,
}


def propose_helper_extraction(source: str, *, origin_symbol: str, proposed_symbol: str, recipe: dict) -> dict | None:
    handler = _HANDLERS.get(str(recipe.get('operation_kind') or ''))
    if handler is None:
        return None
    return validate_helper_proposal(handler(source, origin_symbol=origin_symbol,
                                           proposed_symbol=proposed_symbol, recipe=recipe))
