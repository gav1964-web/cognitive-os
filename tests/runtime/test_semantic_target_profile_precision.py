from runtime.semantic_target_profiles import has_profile


def test_trace_loader_is_not_classified_as_debug_wrapper():
    assert has_profile("pkg/traces.py:load_trace", "debug_trace_wrapper_boundary") is False
    assert has_profile("boltons/debugutils.py:wrap_trace", "debug_trace_wrapper_boundary") is True
