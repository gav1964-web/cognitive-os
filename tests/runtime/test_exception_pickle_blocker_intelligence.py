from __future__ import annotations

from tests.runtime.exception_pickle_blocker_intelligence_helpers import *

def test_blocker_intelligence_ranks_admitted_object_frontier(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class BodyError(Exception):\n"
        "    def __init__(self, body):\n"
        "        self.message = body['message']\n"
        "        super().__init__(self.message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "BodyError",
                "required_constructor_parameters": ["body"],
                "stored_constructor_parameters": ["body"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:BodyError.__init__",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )
    admission = tmp_path / "admission.json"
    admission.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAdmission",
            "source_apply": False,
            "kb_promotion": False,
            "admitted_contracts": {
                "pkg::errors.py:BodyError.__init__": {
                    "project": "pkg",
                    "target": "errors.py:BodyError.__init__",
                    "contracts": [{
                        "parameter": "body",
                        "contract_kind": "mapping_object",
                        "evidence": {"mapping_keys": ["message"]},
                    }],
                }
            },
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
        object_contract_admission_path=admission,
    )

    assert report["status"] == "ready"
    assert report["blocked_case_count"] == 1
    assert report["recommended_next_operator"]["lane"] == "admitted_object_contract_replay_frontier"
    assert report["cases"][0]["unsupported_sample_inputs"] == []
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False


def test_blocker_intelligence_separates_constructor_and_import_lanes(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class MissingStored(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.message = f'value={value}'\n"
        "        super().__init__(self.message)\n"
        "\n"
        "class ImportBlocked(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "MissingStored",
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": [],
                    "formatted_super_argument": True,
                },
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "ImportBlocked",
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
            ],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:MissingStored.__init__",
                    "blocker_kind": "constructor_inputs_not_replayable",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:ImportBlocked.__init__",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["next_operator_lane_summary"] == {
        "import_dependency_isolation_candidate": 1,
        "self_assignment_extraction_candidate": 1,
    }
    assert report["import_isolation_summary"]["case_count"] == 1
    assert report["import_isolation_summary"]["subtype_summary"] == {
        "dependency_unavailable": 1,
    }
    by_target = {case["target"]: case for case in report["cases"]}
    assert by_target["errors.py:MissingStored.__init__"]["missing_constructor_inputs"] == ["value"]
    assert "derived_self_assignment" in by_target["errors.py:MissingStored.__init__"]["source_facts"]["fact_tags"]


def test_blocker_intelligence_marks_target_path_import_root_as_project_local(tmp_path: Path):
    project = tmp_path / "proj"
    package = project / "backend" / "app" / "services"
    package.mkdir(parents=True)
    (package / "jobs.py").write_text(
        "class JobCancelledError(Exception):\n"
        "    def __init__(self, job_id):\n"
        "        self.job_id = job_id\n"
        "        super().__init__(job_id)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "proj",
                "project_root": "proj",
                "path": "backend/app/services/jobs.py",
                "class_name": "JobCancelledError",
                "required_constructor_parameters": ["job_id"],
                "stored_constructor_parameters": ["job_id"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "proj",
                "target": "backend/app/services/jobs.py:JobCancelledError.__init__",
                "blocker_kind": "semantic_replay_dependency_unavailable",
            }],
        }),
        encoding="utf-8",
    )
    report_dir = tmp_path / "artifacts" / "project_development"
    report_dir.mkdir(parents=True)
    (report_dir / "exception_pickle_active_application_20260903T000000000000Z.json").write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationTrial",
            "generated_at": "2026-09-03T00:00:00+00:00",
            "attempts": [{
                "candidate": {
                    "project": "proj",
                    "target": "backend/app/services/jobs.py:JobCancelledError.__init__",
                },
                "project_native_semantic_replay": {
                    "stderr": "ModuleNotFoundError: No module named 'app'",
                },
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    profile = report["cases"][0]["import_isolation_profile"]
    assert profile["missing_import"] == "app"
    assert profile["missing_import_kind"] == "project_local_dependency"


def test_blocker_intelligence_separates_sample_supported_readmission(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class OutputError(Exception):\n"
        "    def __init__(self, output):\n"
        "        self.output = output\n"
        "        super().__init__(output)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "OutputError",
                "required_constructor_parameters": ["output"],
                "stored_constructor_parameters": ["output"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:OutputError.__init__",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["next_operator_lane_summary"] == {"patch_shape_operator_candidate": 1}
    assert report["recommended_next_operator"]["lane"] == "patch_shape_operator_candidate"
    assert report["readmission_frontier_summary"]["case_count"] == 0
    assert report["readmission_frontier_summary"]["ready_now_count"] == 0
    assert report["readmission_frontier_summary"]["subtype_summary"] == {}
    assert report["cases"][0]["readmission_profile"] is None


def test_blocker_intelligence_readmits_supported_static_patch_shape(tmp_path: Path):
    catalog = tmp_path / "knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps({
            "schema_version": "exception_pickle_reconstruction_patterns.v1",
            "status": "active",
            "operator": {
                "id": "preserve_exception_constructor_reconstruction",
                "status": "validated_active",
                "hypothesis_kind": "exception_pickle_reconstruction_boundary",
                "reconstruction_method": "__reduce__",
                "state_strategy": "reuse_direct_assignments",
                "applicability": {"maximum_required_constructor_inputs": 4},
            },
            "safety": {
                "source_apply_allowed": False,
                "automatic_runtime_mutation_allowed": False,
                "requires_sandbox_patch": True,
                "requires_semantic_replay": True,
            },
        }),
        encoding="utf-8",
    )
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class MessageOnlyError(Exception):\n"
        "    def __init__(self, message):\n"
        "        super().__init__()\n"
        "        self.message = message\n"
        "\n"
        "    def __str__(self):\n"
        "        return str(self.message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "MessageOnlyError",
                "required_constructor_parameters": ["message"],
                "stored_constructor_parameters": ["message"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:MessageOnlyError.__init__",
                "blocker_kind": "static_patch_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["next_operator_lane_summary"] == {"sample_supported_readmission_frontier": 1}
    assert report["recommended_next_operator"]["lane"] == "sample_supported_readmission_frontier"
    assert report["cases"][0]["static_patch_readmission_supported"] is True
    assert report["cases"][0]["readmission_profile"]["patchable"] is True
