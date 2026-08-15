from runtime.dependency_boundary_profile import build_dependency_boundary_profile
from runtime.implementation_plan_builder import build_implementation_plan
from runtime.programmer_patch_strategy import build_patch_strategy


def test_dependency_boundary_profile_describes_resolution_without_install_authority():
    profile = build_dependency_boundary_profile(
        {
            "candidate": "pkg/adapter.py:run",
            "dependency_readiness": {
                "status": "missing_external",
                "analysis": "static_import_graph_no_project_import",
                "local_modules_scanned": 3,
                "external_imports": ["optional_sdk"],
                "missing_external_modules": ["optional_sdk"],
            },
            "ranked_candidates": [
                {"source": "pkg/adapter.py:run", "score": 60},
                {
                    "source": "pkg/core.py:normalize",
                    "score": 55,
                    "dependency_readiness": {"status": "ready", "missing_external_modules": []},
                },
            ],
        }
    )

    assert profile["artifact_type"] == "DependencyBoundaryProfile"
    assert profile["status"] == "resolution_required"
    assert profile["missing_modules"] == ["optional_sdk"]
    assert profile["ranked_alternatives"][0]["readiness_status"] == "ready"
    assert "auto_install_dependency" in profile["forbidden_actions"]
    assert "no_install_or_source_mutation" in profile["authority"]


def test_dependency_boundary_profile_is_not_required_for_ready_target():
    profile = build_dependency_boundary_profile(
        {"candidate": "pkg/core.py:run", "dependency_readiness": {"status": "ready"}}
    )

    assert profile == {
        "artifact_type": "DependencyBoundaryProfile",
        "status": "not_required",
        "target": "pkg/core.py:run",
        "missing_modules": [],
    }


def test_executor_strategy_consumes_existing_dependency_profile(tmp_path):
    profile = build_dependency_boundary_profile(
        {
            "candidate": "pkg/adapter.py:run",
            "dependency_readiness": {"missing_external_modules": ["optional_sdk"]},
        }
    )
    proposal = build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={"dependency_boundary_profile": profile},
        implementation_plan={
            "implementation_target": {"candidate": "pkg/adapter.py:run"},
            "dependency_boundary_profile": profile,
        },
        test_plan={},
        synthesis={"status": "prepared", "reason": "guard"},
        acceptance_summary={
            "signal_strength": "meta_only",
            "skipped_reason_counts": {"import_failed_missing_module": 1},
        },
    )

    assert proposal["dependency_boundary_profile"]["status"] == "resolution_required"
    assert proposal["deterministic_strategy"]["action"] == "resolve_dependency_boundary_from_profile"
    assert proposal["deterministic_strategy"]["reason"] == "dependency_profile_requires_resolution"


def test_implementation_plan_preserves_dependency_profile():
    profile = build_dependency_boundary_profile(
        {
            "candidate": "pkg/adapter.py:run",
            "dependency_readiness": {"missing_external_modules": ["optional_sdk"]},
        }
    )
    plan = build_implementation_plan(
        technical_spec={
            "artifact_type": "TechnicalSpec",
            "requirements": [],
            "acceptance_criteria": [],
            "extraction_contract": {
                "candidate": "pkg/adapter.py:run",
                "input_contract": {"value": "str"},
                "output_contract": {"result": "str"},
            },
            "implementation_handoff": {"patch_scope": ["pkg/adapter.py:run"]},
            "dependency_boundary_profile": profile,
        }
    )

    assert plan["dependency_boundary_profile"] == profile
