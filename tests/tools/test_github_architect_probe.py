from __future__ import annotations

from tools.github_architect_probe import _library_surface_present, _project_report_quality, _quality_score


def test_library_surface_counts_as_entry_boundary_for_python_package(tmp_path):
    project = tmp_path / "sample"
    package = project / "src" / "sample"
    package.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    report = {
        "summary": {"languages": ["Python"], "entrypoints": []},
        "answers": {"1_scope": {"code_areas": {"core_logic": ["src/sample/core.py"]}}},
    }

    assert _library_surface_present(project, report, ["src/sample/core.py:run"])
    report_quality = {
        "answers": {
            "1_scope": {"main_task": "Provide a sample package API.", "supported_scenarios": ["import API", "run transform"]},
            "2_execution": {"primary_execution_path": ["import package", "call public function", "return result"]},
            "3_capabilities": {
                "atomic_reusable_capabilities": ["src/sample/core.py:run", "src/sample/core.py:validate"],
                "pure_transforms": ["src/sample/core.py:parse"],
            },
            "6_runtime_extraction_readiness": {"dataflows": ["input -> output"]},
        }
    }
    assert _project_report_quality(report_quality)["score"] == 1.0
    assert _quality_score([], True, ["src/sample/core.py:run"], {"src/sample/core.py": {}}, [], {"score": 1.0}) == 1.0


def test_library_surface_does_not_hide_missing_capability_model(tmp_path):
    project = tmp_path / "sample"
    package = project / "src" / "sample"
    package.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    report = {"summary": {"languages": ["Python"], "entrypoints": []}}

    assert not _library_surface_present(project, report, [])
    assert _quality_score([], False, [], {}, [], {"score": 0.0}) == 0.2


def test_project_report_quality_penalizes_generic_scope_and_weak_execution():
    report = {
        "answers": {
            "1_scope": {
                "main_task": "Run project-specific Python workflows through detected entrypoints ().",
                "supported_scenarios": [],
            },
            "2_execution": {"primary_execution_path": ["not enough evidence"]},
            "3_capabilities": {"atomic_reusable_capabilities": []},
            "6_runtime_extraction_readiness": {},
        }
    }

    quality = _project_report_quality(report)

    assert quality["score"] < 0.5
    assert "generic_main_task" in quality["issues"]
    assert "weak_execution_path" in quality["issues"]


def test_project_report_quality_counts_minimal_extraction_plan_capabilities():
    report = {
        "answers": {
            "1_scope": {
                "main_task": "Provide package resource access for Python library consumers.",
                "supported_scenarios": ["import API", "read resource"],
            },
            "2_execution": {"primary_execution_path": ["import package", "call public function", "return resource"]},
            "3_capabilities": {"atomic_reusable_capabilities": []},
            "6_runtime_extraction_readiness": {
                "data_lifecycle": [{"stage": "call"}],
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [
                        {"capability": "pkg/core.py:where"},
                        {"capability": "pkg/core.py:contents"},
                        {"capability": "pkg/core.py:exit_ctx"},
                    ]
                },
            },
        }
    }

    quality = _project_report_quality(report)

    assert quality["score"] == 1.0
    assert "thin_capability_model" not in quality["issues"]
