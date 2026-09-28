from __future__ import annotations

from pathlib import Path

from runtime.module_script_boundary import enrich_module_script_readiness


def _report(project: Path, entrypoint: str = "backup.py") -> dict:
    return {
        "summary": {"root": project.as_posix(), "entrypoints": [entrypoint]},
        "source_health": {
            "status": "clean", "project_shape": "single_project", "inaccessible_count": 0,
        },
        "answers": {
            "2_execution": {"entrypoints": [entrypoint]},
            "6_runtime_extraction_readiness": {
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [], "blocked_by": ["no_safe_python_candidate"],
                }
            },
        },
    }


def test_executable_module_becomes_process_boundary(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "backup.py").write_text(
        "import sys\nfrom pathlib import Path\nout = sys.argv[1]\nPath(out).write_text('ok')\n",
        encoding="utf-8",
    )

    result = enrich_module_script_readiness(_report(project))
    readiness = result["answers"]["6_runtime_extraction_readiness"]
    candidate = readiness["minimal_extraction_plan"]["capabilities_to_extract"][0]

    assert candidate["capability"] == "backup.py"
    assert candidate["candidate_kind"] == "module_script_process_boundary"
    assert readiness["minimal_extraction_plan"]["blocked_by"] == []
    assert readiness["process_boundary_candidates"][0]["target"] == "backup.py"


def test_declaration_only_module_remains_blocked(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "backup.py").write_text("DEFAULT_LIMIT = 10\n", encoding="utf-8")

    result = enrich_module_script_readiness(_report(project))
    plan = result["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"]

    assert plan["capabilities_to_extract"] == []
    assert plan["blocked_by"] == ["no_safe_python_candidate"]
