from __future__ import annotations

from runtime.contract_archetype_inference import (
    archetype_ranking_adjustments,
    contract_archetype_for_target,
)


def test_tokenizer_method_has_bounded_text_transform_contract():
    target = "package/tokenizers/bert_tokenizer.py:BertTokenizer._tokenize"

    contract = contract_archetype_for_target(target)
    ranking = archetype_ranking_adjustments(target)

    assert contract["contract_family"] == "text_tokenization_transform"
    assert contract["input_contract"]["text"].startswith("TextInput")
    assert contract["output_contract"]["tokens"].startswith("TokenSequence")
    assert ranking["score_delta"] >= 30


def test_schema_generator_has_structured_projection_contract():
    target = "package/lib.py:Schema._schema_gen"

    contract = contract_archetype_for_target(target)
    ranking = archetype_ranking_adjustments(target)

    assert contract["contract_family"] == "structured_schema_projection"
    assert contract["input_contract"]["value"].startswith("StructuredValue")
    assert contract["output_contract"]["schema"].startswith("SchemaProjection")
    assert ranking["score_delta"] >= 30
