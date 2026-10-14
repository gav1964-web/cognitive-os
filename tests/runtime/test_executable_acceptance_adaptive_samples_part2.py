from __future__ import annotations

from tests.runtime.executable_acceptance_adaptive_samples_helpers import *

def test_attribute_unpack_shape_overrides_generic_sequence_contract_sample():
    from runtime.executable_acceptance_support import positive_case_binding

    def ratio(image):
        width, height = image.size
        return width / height

    obligations = [{
        "target": "module.py:ratio",
        "kind": "positive_contract_case",
        "given": {"image": ["sample"]},
    }]
    fixture = {
        "__fixture__": "declared_model",
        "type": "AcceptanceInput",
        "fields": {"size": [1.0, 1.0]},
    }
    inferred = {
        "image": {"value": fixture, "source": "ast_parameter_attribute_unpack"},
    }

    binding = positive_case_binding(ratio, "module.py:ratio", obligations, inferred)

    assert binding["overrides"] == {"image": fixture}


def test_literal_membership_domain_overrides_empty_contract_sample():
    from runtime.executable_acceptance_support import positive_case_binding

    def validate(level):
        return level

    obligations = [{
        "target": "module.py:validate",
        "kind": "positive_contract_case",
        "given": {"level": ""},
    }]
    inferred = {
        "level": {"value": "high", "source": "ast_literal_membership_domain"},
    }

    binding = positive_case_binding(validate, "module.py:validate", obligations, inferred)

    assert binding["overrides"] == {"level": "high"}


def test_string_formatting_does_not_override_literal_domain(tmp_path):
    path = tmp_path / "module.py"
    path.write_text(
        "def choose(mode):\n"
        "    if mode == 'longest': return 1\n"
        "    raise ValueError('unknown mode %r' % mode)\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "choose") == {
        "mode": {"value": "longest", "source": "ast_comparison_literal"}
    }
