from runtime.role_evaluation_regression import build_role_evaluation_regression


def _evaluation(score: float, maturity: str = "mature") -> dict:
    cell = {
        "role_id": "architect",
        "project_stratum": "framework_plugin_build",
        "score": score,
        "maturity": maturity,
    }
    return {
        "cells": [cell],
        "known_strata_regression_baseline": {
            "protected_cell_count": 1,
            "protected_cells": [cell],
        },
    }


def test_role_regression_preserves_protected_cell() -> None:
    report = build_role_evaluation_regression(_evaluation(9.7), _evaluation(9.8))

    assert report["status"] == "passed"
    assert report["regression_count"] == 0


def test_role_regression_rejects_score_drop() -> None:
    report = build_role_evaluation_regression(_evaluation(9.7), _evaluation(9.6))

    assert report["status"] == "failed"
    assert report["regressions"][0]["actual_score"] == 9.6
