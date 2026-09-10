from __future__ import annotations

from tests.runtime.exception_pickle_blocker_intelligence_helpers import *

def test_blocker_intelligence_routes_behavior_mismatch_after_source_aware_sample_to_contrast(
    tmp_path: Path,
):
    project = tmp_path / "reader"
    project.mkdir()
    (project / "errors.py").write_text(
        "class ReaderError(Exception):\n"
        "    def __init__(self, error_type, line):\n"
        "        self.error_type = error_type\n"
        "        self.line = line\n"
        "        super().__init__(f'{error_type}: {line[:100]}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "reader",
                "project_root": "reader",
                "path": "errors.py",
                "class_name": "ReaderError",
                "required_constructor_parameters": ["error_type", "line"],
                "stored_constructor_parameters": ["error_type", "line"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "reader",
                "target": "errors.py:ReaderError.__init__",
                "blocker_kind": "semantic_replay_behavior_mismatch",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["next_operator_lane_summary"] == {"semantic_behavior_contrast_research": 1}
    assert report["cases"][0]["source_aware_sample_override"] is True
    assert report["cases"][0]["materializer_behavior_readmission_delta"] is True
    assert report["readmission_frontier_summary"]["case_count"] == 0


def test_blocker_intelligence_routes_behavior_mismatch_after_known_object_sample_delta_to_contrast(
    tmp_path: Path,
):
    project = tmp_path / "flags"
    project.mkdir()
    (project / "errors.py").write_text(
        "class TooManyFlags(Exception):\n"
        "    def __init__(self, flag, values):\n"
        "        self.flag = flag\n"
        "        self.values = values\n"
        "        super().__init__(f'expected {flag.max_args} got {len(values)}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "flags",
                "project_root": "flags",
                "path": "errors.py",
                "class_name": "TooManyFlags",
                "required_constructor_parameters": ["flag", "values"],
                "stored_constructor_parameters": ["flag", "values"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "flags",
                "target": "errors.py:TooManyFlags.__init__",
                "blocker_kind": "semantic_replay_behavior_mismatch",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["next_operator_lane_summary"] == {"semantic_behavior_contrast_research": 1}
    assert report["cases"][0]["materializer_behavior_readmission_delta"] is True


def test_blocker_intelligence_routes_target_class_missing_attribute_to_state_contract(
    tmp_path: Path,
):
    project = tmp_path / "oauth"
    project.mkdir()
    (project / "errors.py").write_text(
        "class OAuth2Error(Exception):\n"
        "    description = 'sample'\n"
        "    def __init__(self, request):\n"
        "        self.request = request\n"
        "        self.error_uri = request.settings.ERROR_URI + self.error\n"
        "        super().__init__(self.error)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "oauth",
                "project_root": "oauth",
                "path": "errors.py",
                "class_name": "OAuth2Error",
                "required_constructor_parameters": ["request"],
                "stored_constructor_parameters": ["request"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "oauth",
                "target": "errors.py:OAuth2Error.__init__",
                "blocker_kind": "semantic_replay_behavior_mismatch",
                "project_native_semantic_replay": {
                    "stderr": "AttributeError: 'OAuth2Error' object has no attribute 'error'",
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

    assert report["next_operator_lane_summary"] == {"class_state_contract_research": 1}
    assert report["recommended_next_operator"]["lane"] == "class_state_contract_research"
    assert report["readmission_frontier_summary"]["case_count"] == 0


def test_blocker_intelligence_routes_attribute_base_classes_to_import_isolation(
    tmp_path: Path,
):
    project = tmp_path / "spackish"
    project.mkdir()
    (project / "errors.py").write_text(
        "import external\n\n"
        "class PackageMeta(external.MetaA, external.MetaB):\n"
        "    pass\n\n"
        "class PackageStillNeededError(Exception):\n"
        "    def __init__(self, spec, dependents):\n"
        "        self.spec = spec\n"
        "        self.dependents = dependents\n"
        "        super().__init__(f'{spec.name}: {dependents.keys()}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "spackish",
                "project_root": "spackish",
                "path": "errors.py",
                "class_name": "PackageStillNeededError",
                "required_constructor_parameters": ["spec", "dependents"],
                "stored_constructor_parameters": ["spec", "dependents"],
                "formatted_super_argument": True,
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "spackish",
                "target": "errors.py:PackageStillNeededError.__init__",
                "blocker_kind": "semantic_replay_behavior_mismatch",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["next_operator_lane_summary"] == {"import_dependency_isolation_candidate": 1}
    assert report["cases"][0]["readmission_profile"] is None
    assert report["cases"][0]["import_isolation_profile"]["subtype"] == "attribute_base_metaclass_risk"
    assert report["import_isolation_summary"]["subtype_summary"] == {
        "attribute_base_metaclass_risk": 1,
    }
    assert "attribute_base_class_definition" in report["cases"][0]["source_facts"]["fact_tags"]


def test_blocker_intelligence_extracts_missing_imports_from_active_reports(tmp_path: Path):
    project = tmp_path / "missingdep"
    project.mkdir()
    (project / "errors.py").write_text(
        "class MissingDepError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "missingdep",
                "project_root": "missingdep",
                "path": "errors.py",
                "class_name": "MissingDepError",
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
                "project": "missingdep",
                "target": "errors.py:MissingDepError.__init__",
                "blocker_kind": "semantic_replay_dependency_unavailable",
            }],
        }),
        encoding="utf-8",
    )
    reports = tmp_path / "artifacts" / "project_development"
    reports.mkdir(parents=True)
    (reports / "exception_pickle_active_application_20260902T010101000000Z.json").write_text(
        json.dumps({
            "generated_at": "2026-09-02T01:01:01+00:00",
            "attempts": [{
                "candidate": {
                    "project": "missingdep",
                    "target": "errors.py:MissingDepError.__init__",
                },
                "project_native_semantic_replay": {
                    "stderr": "ModuleNotFoundError: No module named 'missing_runtime'",
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

    assert report["cases"][0]["import_isolation_profile"]["missing_import"] == "missing_runtime"
    assert report["cases"][0]["import_isolation_profile"]["missing_import_kind"] == "external_dependency"
    assert report["import_isolation_summary"]["missing_import_kind_summary"] == {
        "external_dependency": 1
    }
    assert report["import_isolation_summary"]["top_missing_imports"] == [
        {"value": "missing_runtime", "count": 1}
    ]


def test_blocker_intelligence_classifies_stdlib_symbol_missing_imports(tmp_path: Path):
    project = tmp_path / "compatdep"
    project.mkdir()
    (project / "errors.py").write_text(
        "class CompatDepError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "compatdep",
                "project_root": "compatdep",
                "path": "errors.py",
                "class_name": "CompatDepError",
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
                "project": "compatdep",
                "target": "errors.py:CompatDepError.__init__",
                "blocker_kind": "semantic_replay_import_failed",
                "project_native_semantic_replay": {
                    "stderr": "ImportError: cannot import name 'GenericAlias' from 'types'",
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
    assert profile["missing_import"] == "types:GenericAlias"
    assert profile["missing_import_kind"] == "stdlib_symbol_compat"
    assert report["import_isolation_summary"]["missing_import_kind_summary"] == {
        "stdlib_symbol_compat": 1
    }
