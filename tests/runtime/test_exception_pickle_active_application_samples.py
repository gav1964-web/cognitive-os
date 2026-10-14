from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_uses_string_sample_for_ambiguous_code_name(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "api"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ApiError(Exception):\n"
        "    def __init__(self, action, code, message):\n"
        "        self.action = action\n"
        "        self.code = code\n"
        "        self.message = message\n"
        "        super().__init__(f'{action}: {code.lower()}: {message}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "api",
                "project_root": "api",
                "path": "pkg.py",
                "class_name": "ApiError",
                "score": 7,
                "required_constructor_parameters": ["action", "code", "message"],
                "stored_constructor_parameters": ["action", "code", "message"],
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


def test_active_application_uses_source_aware_string_sample_for_sliced_line(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "reader"
    project.mkdir()
    (project / "pkg.py").write_text(
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
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "reader",
                "project_root": "reader",
                "path": "pkg.py",
                "class_name": "ReaderError",
                "score": 7,
                "required_constructor_parameters": ["error_type", "line"],
                "stored_constructor_parameters": ["error_type", "line"],
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


def test_active_application_replays_target_file_when_package_init_import_fails(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "pkg-project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text(
        "import missing_dependency_for_replay\n",
        encoding="utf-8",
    )
    (project / "pkg" / "errors.py").write_text(
        "class PackageInitError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "pkg-project",
                "project_root": "pkg-project",
                "path": "pkg/errors.py",
                "class_name": "PackageInitError",
                "score": 7,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
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

    replay = report["selected_application"]["project_native_semantic_replay"]
    assert report["status"] == "applied_active_kb"
    assert '"import_strategy": "direct_file_import"' in replay["stdout"]


def test_active_application_accepts_self_reference_exception_args(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "service-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ServiceNotFound(Exception):\n"
        "    def __init__(self, domain, service):\n"
        "        self.domain = domain\n"
        "        self.service = service\n"
        "        super().__init__(self, f'Service {domain}.{service} not found')\n"
        "    def __str__(self):\n"
        "        return f'Unable to find service {self.domain}.{self.service}'\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "service-project",
                "project_root": "service-project",
                "path": "pkg.py",
                "class_name": "ServiceNotFound",
                "score": 7,
                "required_constructor_parameters": ["domain", "service"],
                "stored_constructor_parameters": ["domain", "service"],
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

    replay = report["selected_application"]["project_native_semantic_replay"]
    assert report["status"] == "applied_active_kb"
    assert '"normalized_args_before": ["<self>",' in replay["stdout"]


def test_active_application_serializes_self_only_exception_args_cycle_safely(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "self-only-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class SelfOnlyError(Exception):\n"
        "    def __init__(self, response):\n"
        "        super().__init__(self)\n"
        "        self.response = response\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "self-only-project",
                "project_root": "self-only-project",
                "path": "pkg.py",
                "class_name": "SelfOnlyError",
                "score": 7,
                "required_constructor_parameters": ["response"],
                "stored_constructor_parameters": ["response"],
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

    replay = report["selected_application"]["project_native_semantic_replay"]
    assert report["status"] == "applied_active_kb"
    assert '"args_before": ["<self>"]' in replay["stdout"]
    assert '"normalized_args_after": ["<self>"]' in replay["stdout"]


def test_active_application_replays_keyword_only_constructor_inputs(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "keyword-only-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class KeywordOnlyError(RuntimeError):\n"
        "    def __init__(self, *, message, context):\n"
        "        self.message = message\n"
        "        self.context = context\n"
        "        super().__init__(f'{message}: {context}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "keyword-only-project",
                "project_root": "keyword-only-project",
                "path": "pkg.py",
                "class_name": "KeywordOnlyError",
                "score": 7,
                "required_constructor_parameters": ["message", "context"],
                "stored_constructor_parameters": ["message", "context"],
                "formatted_super_argument": True,
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
    assert '"args_before": ["sample-message: sample-context"]' in replay["stdout"]


