from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_direct_file_stubs_constructor_local_imports(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "local-import-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class LocalImportError(Exception):\n"
        "    def __init__(self, output, stages):\n"
        "        from funcy import first\n"
        "        assert first\n"
        "        stage_names = '\\n'.join(['\\t- ' + s.addressing for s in stages])\n"
        "        super().__init__(f\"output '{output}' is specified in:\\n{stage_names}\")\n"
        "        self.output = output\n"
        "        self.stages = stages\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "local-import-project",
                "project_root": "local-import-project",
                "path": "pkg.py",
                "class_name": "LocalImportError",
                "score": 7,
                "required_constructor_parameters": ["output", "stages"],
                "stored_constructor_parameters": ["output", "stages"],
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


def test_active_application_samples_migration_dir_and_version(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "migration-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class UnappliedMigrationsError(Exception):\n"
        "    def __init__(self, dir: str, version: int):\n"
        "        self.dir = dir\n"
        "        self.version = version\n"
        "        super().__init__(f'Unapplied migrations in {dir}, starting with version {version}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "migration-project",
                "project_root": "migration-project",
                "path": "pkg.py",
                "class_name": "UnappliedMigrationsError",
                "score": 7,
                "required_constructor_parameters": ["dir", "version"],
                "stored_constructor_parameters": ["dir", "version"],
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


def test_active_application_samples_missing_services_list(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "service-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ServiceNotEnabledException(Exception):\n"
        "    def __init__(self, missing_services, auth_url):\n"
        "        self.missing_services = missing_services\n"
        "        self.auth_url = auth_url\n"
        "        services_str = ', '.join(missing_services)\n"
        "        super().__init__(f'Required services not enabled: {services_str}. Please enable them at: {auth_url}')\n",
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
                "class_name": "ServiceNotEnabledException",
                "score": 7,
                "required_constructor_parameters": ["missing_services", "auth_url"],
                "stored_constructor_parameters": ["missing_services", "auth_url"],
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


def test_active_application_samples_response_object_contract(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "response-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from json import dumps\n\n"
        "class HttpRequestError(Exception):\n"
        "    def __init__(self, response):\n"
        "        self.response = response\n"
        "        self.message = self._format_error_message()\n"
        "        super().__init__(self.message)\n"
        "    def _format_error_message(self):\n"
        "        body = self._get_response_body()\n"
        "        base_message = f'{self.response.status_code} response from {self.response.url}'\n"
        "        if body:\n"
        "            return f'{base_message}. Error response body: {body}'\n"
        "        return base_message\n"
        "    def _get_response_body(self):\n"
        "        if not self.response.content:\n"
        "            return None\n"
        "        return dumps(self.response.json(), indent=4)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "response-project",
                "project_root": "response-project",
                "path": "pkg.py",
                "class_name": "HttpRequestError",
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

    assert report["status"] == "applied_active_kb"


def test_active_application_stops_after_replay_blocker_budget(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "dep-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "import missing_dependency_for_replay\n\n"
        "class DepError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n\n"
        "class NextError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "dep-project",
                    "project_root": "dep-project",
                    "path": "pkg.py",
                    "class_name": "DepError",
                    "score": 10,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "dep-project",
                    "project_root": "dep-project",
                    "path": "pkg.py",
                    "class_name": "NextError",
                    "score": 9,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
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
        maximum_attempts=2,
        maximum_replay_blockers=1,
        allow_target_import_stubs=False,
    )

    assert report["status"] == "blocked"
    assert report["attempt_count"] == 1
    assert report["replay_blocker_limit_reached"] is True
    assert report["attempts"][0]["blocker_kind"] == "semantic_replay_dependency_unavailable"


def test_active_application_prioritizes_dependency_light_replay_candidate(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    heavy = tmp_path / "heavy"
    (heavy / "pkg").mkdir(parents=True)
    (heavy / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (heavy / "pkg" / "errors.py").write_text(
        "import missing_dependency_for_replay\n\n"
        "class HeavyError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    light = tmp_path / "light"
    light.mkdir()
    (light / "pkg.py").write_text(
        "class LightError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n",
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
                    "path": "pkg/errors.py",
                    "class_name": "HeavyError",
                    "score": 100,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "light",
                    "project_root": "light",
                    "path": "pkg.py",
                    "class_name": "LightError",
                    "score": 1,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
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
        maximum_attempts=1,
    )

    assert report["status"] == "applied_active_kb"
    assert (
        report["selection_policy"]
        == "strict_readmission_precheck_patchability_dependency_light_and_project_static_budget"
    )
    assert report["selected_application"]["candidate"]["project"] == "light"


