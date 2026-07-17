from __future__ import annotations

from runtime.target_quality import target_quality_report


def test_target_quality_marks_representative_target_good():
    report = target_quality_report(
        {
            "selected_extraction_candidate": "src/prefect/task_engine.py:_create_task_run_locally",
            "implementation_binding_status": "bound_to_extraction_contract",
            "test_has_contract_matrix": True,
            "test_has_negative_tests_for_target": True,
        }
    )

    assert report["status"] == "good"
    assert "representative domain target" in " ".join(report["reasons"])


def test_target_quality_flags_utility_target_as_suspicious():
    report = target_quality_report(
        {
            "selected_extraction_candidate": "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap",
            "implementation_binding_status": "bound_to_extraction_contract",
            "test_has_contract_matrix": True,
            "test_has_negative_tests_for_target": True,
        }
    )

    assert report["status"] == "suspicious"
    assert "suspicious utility/support target" in " ".join(report["reasons"])


def test_target_quality_marks_missing_target_blocked():
    report = target_quality_report({"selected_extraction_candidate": ""})

    assert report["status"] == "blocked"
