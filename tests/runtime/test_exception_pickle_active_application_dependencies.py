from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_requires_dependency_light_readmission(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    heavy = tmp_path / "heavy"
    heavy.mkdir()
    (heavy / "pkg.py").write_text(
        "import dep_a\nimport dep_b\nimport dep_c\nimport dep_d\n\n"
        "class HeavyResponseError(Exception):\n"
        "    def __init__(self, response):\n"
        "        self.response = response\n"
        "        super().__init__(response)\n",
        encoding="utf-8",
    )
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "pkg.py").write_text(
        "class CleanError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "heavy",
                    "project_root": "heavy",
                    "path": "pkg.py",
                    "class_name": "HeavyResponseError",
                    "score": 100,
                    "required_constructor_parameters": ["response"],
                    "stored_constructor_parameters": ["response"],
                },
                {
                    "canonical_project": "clean",
                    "project_root": "clean",
                    "path": "pkg.py",
                    "class_name": "CleanError",
                    "score": 1,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
            ],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [],
            "blocked_cases": [{
                "project": "heavy",
                "target": "pkg.py:HeavyResponseError.__init__",
                "status": "blocked_precheck",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
    )

    assert report["status"] == "applied_active_kb"
    assert report["attempt_count"] == 1
    assert report["selected_application"]["candidate"]["project"] == "clean"


def test_active_application_prefers_direct_file_replay_for_package_init_risk(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "package-risk"
    package = project / "pkg" / "sub"
    package.mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text(
        "raise SystemExit('package import side effect')\n",
        encoding="utf-8",
    )
    (package / "errors.py").write_text(
        "class PackageRiskError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "package-risk",
                "project_root": "package-risk",
                "path": "pkg/sub/errors.py",
                "class_name": "PackageRiskError",
                "score": 1,
                "required_constructor_parameters": ["message"],
                "stored_constructor_parameters": ["message"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    assert report["status"] == "applied_active_kb"
    replay = report["selected_application"]["project_native_semantic_replay"]
    assert '"import_strategy": "direct_file_import"' in replay["stdout"]
    assert '"import_error": "preferred_direct_file_import"' in replay["stdout"]


def test_active_application_consumes_admitted_mapping_object_contract(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "body-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class BodyError(Exception):\n"
        "    def __init__(self, body):\n"
        "        self.body = body\n"
        "        self.message = body['message']\n"
        "        self.status = body.get('status')\n"
        "        super().__init__(self.message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "body-project",
                "project_root": "body-project",
                "path": "pkg.py",
                "class_name": "BodyError",
                "score": 7,
                "required_constructor_parameters": ["body"],
                "stored_constructor_parameters": ["body"],
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
                "body-project::pkg.py:BodyError.__init__": {
                    "project": "body-project",
                    "target": "pkg.py:BodyError.__init__",
                    "contracts": [{
                        "parameter": "body",
                        "contract_kind": "mapping_object",
                        "confidence": 0.82,
                        "source_backed": True,
                        "promotion_allowed": False,
                        "evidence": {"mapping_keys": ["message", "status"], "method_calls": []},
                    }],
                }
            },
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
        object_contract_admission_path=admission,
    )

    assert report["status"] == "applied_active_kb"
    selected = report["selected_application"]
    assert selected["object_contracts"]["body"]["contract_kind"] == "mapping_object"
    assert selected["project_native_semantic_replay"]["status"] == "passed"


def test_active_application_samples_exception_alias_parameter_from_source(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "command-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class CommandInvokeError(Exception):\n"
        "    def __init__(self, command, e):\n"
        "        self.original = e\n"
        "        self.command = command\n"
        "        super().__init__(f'Command {command.name!r}: {e.__class__.__name__}: {e}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "command-project",
                "project_root": "command-project",
                "path": "pkg.py",
                "class_name": "CommandInvokeError",
                "score": 7,
                "required_constructor_parameters": ["command", "e"],
                "stored_constructor_parameters": ["command", "e"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["project_native_semantic_replay"]["status"] == "passed"


def test_active_application_samples_revision_text_and_heads(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "revision-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class RangeNotAncestorError(Exception):\n"
        "    def __init__(self, lower, upper):\n"
        "        self.lower = lower\n"
        "        self.upper = upper\n"
        "        super().__init__('Revision %s is not an ancestor of revision %s' % (lower or 'base', upper or 'base'))\n\n"
        "class MultipleHeads(Exception):\n"
        "    def __init__(self, heads, argument):\n"
        "        self.heads = heads\n"
        "        self.argument = argument\n"
        "        super().__init__(\"Multiple heads are present for given argument '%s'; %s\" % (argument, ', '.join(heads)))\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "revision-project",
                    "project_root": "revision-project",
                    "path": "pkg.py",
                    "class_name": "RangeNotAncestorError",
                    "score": 7,
                    "required_constructor_parameters": ["lower", "upper"],
                    "stored_constructor_parameters": ["lower", "upper"],
                },
                {
                    "canonical_project": "revision-project",
                    "project_root": "revision-project",
                    "path": "pkg.py",
                    "class_name": "MultipleHeads",
                    "score": 6,
                    "required_constructor_parameters": ["heads", "argument"],
                    "stored_constructor_parameters": ["heads", "argument"],
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
        maximum_accepted_applications=2,
    )

    assert report["status"] == "applied_active_kb"
    assert report["selected_application_count"] == 2
    assert all(
        selected["project_native_semantic_replay"]["status"] == "passed"
        for selected in report["selected_applications"]
    )


