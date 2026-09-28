from __future__ import annotations

from tests.runtime.semantic_target_profiles_helpers import *

def test_semantic_target_profiles_cover_blind_redteam_40k_gaps():
    cases = {
        "src/awkward/_slicing.py:_normalise_item_bool_to_int": "array_slice_normalization_boundary",
        "src/cffi/backend_ctypes.py:complete_struct_or_union": "ffi_struct_completion_boundary",
        "src/hist/plot.py:plot_ratio_array": "plot_ratio_array_boundary",
        "src/nacl/bindings/crypto_secretstream.py:crypto_secretstream_xchacha20poly1305_pull": "crypto_secretstream_pull_boundary",
        "src/OpenSSL/crypto.py:__setattr__": "crypto_attribute_bridge_boundary",
        "src/protego/_protego.py:_extract_directive": "robots_directive_parser_boundary",
        "src/uproot/behaviors/RNTuple.py:arrays": "scientific_tree_array_read_boundary",
        "src/vector/_compute/lorentz/add.py:dispatch": "vector_compute_dispatch_boundary",
        "numpy/lib/_function_base_impl.py:_quantile": "numeric_array_statistical_transform",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_cover_blind_redteam_40l_gaps():
    cases = {
        "Lib/fontTools/designspaceLib/split.py:_extractSubSpace": "font_designspace_subspace_extraction_boundary",
        "src/PIL/Image.py:convert": "image_mode_conversion_transform",
        "shapely/_ragged_array.py:_get_arrays_multilinestring": "geometry_ragged_array_extraction_boundary",
        "vine/promises.py:throw": "promise_error_propagation_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24
