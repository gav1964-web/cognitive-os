from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_samples_requirements_list(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "requirements-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class RequirementsNotFound(Exception):\n"
        "    def __init__(self, domain, requirements):\n"
        "        self.domain = domain\n"
        "        self.requirements = requirements\n"
        "        super().__init__(f'Requirements for {domain} not found: {requirements}.')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "requirements-project",
                "project_root": "requirements-project",
                "path": "pkg.py",
                "class_name": "RequirementsNotFound",
                "score": 7,
                "required_constructor_parameters": ["domain", "requirements"],
                "stored_constructor_parameters": ["domain", "requirements"],
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


def test_active_application_candidate_key_reprobes_blocked_target(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "reprobe-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ReprobeError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "reprobe-project",
                "project_root": "reprobe-project",
                "path": "pkg.py",
                "class_name": "ReprobeError",
                "score": 7,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
            }],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "reprobe-project",
                "target": "pkg.py:ReprobeError.__init__",
                "blocker_kind": "semantic_replay_behavior_mismatch",
            }],
        }),
        encoding="utf-8",
    )

    ordinary = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "ordinary",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        update_application_ledger=False,
    )
    reprobe = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "reprobe",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        candidate_keys=["reprobe-project::pkg.py:ReprobeError.__init__"],
        update_application_ledger=False,
    )

    assert ordinary["attempt_count"] == 0
    assert reprobe["candidate_keys"] == ["reprobe-project::pkg.py:ReprobeError.__init__"]
    assert reprobe["status"] == "applied_active_kb"
    assert reprobe["selected_application"]["candidate"] == {
        "project": "reprobe-project",
        "score": 7,
        "target": "pkg.py:ReprobeError.__init__",
    }


def test_active_application_direct_file_stub_supports_callable_class_defaults(
    tmp_path: Path,
):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "callable-stub-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from missing.backoff import Backoff\n\n"
        "DEFAULT = Backoff(base=1, cap=2)\n\n"
        "class HttpError(Exception):\n"
        "    def __init__(self, status, url):\n"
        "        self.status = status\n"
        "        self.url = url\n"
        "        super().__init__(f'HTTP {status} for {url}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "callable-stub-project",
                "project_root": "callable-stub-project",
                "path": "pkg.py",
                "class_name": "HttpError",
                "score": 7,
                "required_constructor_parameters": ["status", "url"],
                "stored_constructor_parameters": ["status", "url"],
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
    assert replay["status"] == "passed"
    assert "direct_file_import" in replay["stdout"]


def test_active_application_direct_file_stub_supports_decorator_attributes(
    tmp_path: Path,
):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "decorator-stub-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from missing import util\n\n"
        "class RevisionMap:\n"
        "    @util.memoized_property\n"
        "    def heads(self):\n"
        "        return ()\n\n"
        "class RevisionError(Exception):\n"
        "    def __init__(self, lower, upper):\n"
        "        self.lower = lower\n"
        "        self.upper = upper\n"
        "        super().__init__('Revision %s is not an ancestor of revision %s' % (lower or 'base', upper or 'base'))\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "decorator-stub-project",
                "project_root": "decorator-stub-project",
                "path": "pkg.py",
                "class_name": "RevisionError",
                "score": 7,
                "required_constructor_parameters": ["lower", "upper"],
                "stored_constructor_parameters": ["lower", "upper"],
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


def test_active_application_direct_file_stub_supports_decorator_factories(
    tmp_path: Path,
):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "decorator-factory-stub-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from missing.telemetry import Granularity, trace_method\n\n"
        "class MigratableDB:\n"
        "    @trace_method('MigratableDB.validate_migrations', Granularity.ALL)\n"
        "    def validate_migrations(self):\n"
        "        return None\n\n"
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
                "canonical_project": "decorator-factory-stub-project",
                "project_root": "decorator-factory-stub-project",
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


def test_active_application_direct_file_stub_supports_import_star(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "import-star-stub-project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "errors.py").write_text(
        "from .entity import *\n\n"
        "class JmcomicException(Exception):\n"
        "    def __init__(self, msg, context):\n"
        "        self.msg = msg\n"
        "        self.context = context\n"
        "        super().__init__(msg)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "import-star-stub-project",
                "project_root": "import-star-stub-project",
                "path": "pkg/errors.py",
                "class_name": "JmcomicException",
                "score": 7,
                "required_constructor_parameters": ["msg", "context"],
                "stored_constructor_parameters": ["msg", "context"],
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


def test_active_application_samples_stage_like_collection(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "stage-collection-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class OutputDuplicationError(Exception):\n"
        "    def __init__(self, output, stages):\n"
        "        assert all(hasattr(stage, 'relpath') for stage in stages)\n"
        "        stage_names = '\\n'.join(['\\t- ' + s.addressing for s in stages])\n"
        "        msg = f\"output '{output}' is specified in:\\n{stage_names}\"\n"
        "        super().__init__(msg)\n"
        "        self.stages = stages\n"
        "        self.output = output\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "stage-collection-project",
                "project_root": "stage-collection-project",
                "path": "pkg.py",
                "class_name": "OutputDuplicationError",
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


