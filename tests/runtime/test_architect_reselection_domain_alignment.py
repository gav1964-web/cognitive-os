from runtime.architect_first_slice_reselection import _domain_aligned_sources


def test_scientific_reselection_excludes_unrelated_operational_support():
    sources = [
        "pkg/system/logger.py:init",
        "pkg/math/derivative.py:derivative_stack",
        "pkg/solver.py:solve",
    ]
    architecture_decision = {
        "first_slice_contract": {"knowledge_rule": "scientific_compute_library"}
    }
    policy = {
        "domain_candidate_required_any": {
            "scientific_compute_library": ["math/", "derivative", "solve"]
        }
    }

    assert _domain_aligned_sources(sources, architecture_decision, policy) == [
        "pkg/math/derivative.py:derivative_stack",
        "pkg/solver.py:solve",
    ]


def test_unprofiled_reselection_preserves_candidate_window():
    sources = ["pkg/system/logger.py:init", "pkg/core.py:normalize"]

    assert _domain_aligned_sources(sources, {}, {}) == sources
