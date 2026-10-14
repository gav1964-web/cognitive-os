from pathlib import Path

from runtime.self_improvement_emergent_hypothesis import emergent_hypothesis_redirect


def _observed(root: Path, name: str, signature: str, score: float, *, aligned: bool = True):
    project = root / name
    project.mkdir()
    summary = {
        "project": name,
        "project_min_score": score,
        "portable_signature": signature,
        "matches_hypothesis": False,
        "retrieval_alignment": {"aligned": aligned},
    }
    return project, {"source_fingerprint": name}, summary, True


def test_redirects_to_repeated_low_scoring_aligned_signature(tmp_path: Path):
    signature = "first_slice_reselection_required|pure|insufficient_structural_evidence"
    observed = [_observed(tmp_path, f"project_{index}", signature, 5.0) for index in range(4)]

    result = emergent_hypothesis_redirect(
        observed,
        {"minimum_projects": 4, "minimum_emergent_redirect_projects": 4},
        9.7,
    )

    assert result is not None
    assert result["portable_signature"] == signature
    assert result["failure_class"] == "first_slice_reselection_required"
    assert result["observed_project_count"] == 4
    assert len(result["matching"]) == 4


def test_does_not_merge_high_scoring_drift_or_different_signatures(tmp_path: Path):
    signature = "first_slice_reselection_required|pure|insufficient_structural_evidence"
    observed = [
        _observed(tmp_path, "low", signature, 5.0),
        _observed(tmp_path, "ready", signature, 9.7),
        _observed(tmp_path, "drift", signature, 5.0, aligned=False),
        _observed(tmp_path, "other", "meta_only|pure|insufficient_structural_evidence", 7.5),
    ]

    assert emergent_hypothesis_redirect(
        observed,
        {"minimum_projects": 4, "minimum_emergent_redirect_projects": 4},
        9.7,
    ) is None
