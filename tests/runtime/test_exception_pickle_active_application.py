from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_applies_next_supported_candidate_and_updates_ledger(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    blocked_project = tmp_path / "blocked"
    blocked_project.mkdir()
    (blocked_project / "pkg.py").write_text(
        "class BlockedError(Exception):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )
    applied_project = tmp_path / "applied"
    applied_project.mkdir()
    (applied_project / "pkg.py").write_text(
        "class AppliedError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "blocked",
                    "project_root": "blocked",
                    "path": "pkg.py",
                    "class_name": "BlockedError",
                    "score": 10,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "applied",
                    "project_root": "applied",
                    "path": "pkg.py",
                    "class_name": "AppliedError",
                    "score": 9,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
            ],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        prioritize_patchable_candidates=False,
    )

    assert report["status"] == "applied_active_kb"
    assert report["attempts"][0]["status"] == "blocked_static_patch"
    assert report["selected_application"]["candidate"]["project"] == "applied"
    assert "def __reduce__" not in (applied_project / "pkg.py").read_text(encoding="utf-8")
    payload = json.loads(application_ledger.read_text(encoding="utf-8"))
    assert payload["active_pattern_applied_count"] == 1
    assert payload["active_pattern_blocked_count"] == 1
    assert payload["blocker_summary"] == {"static_patch_shape_unsupported": 1}
    assert payload["blocked_cases"][0]["project"] == "blocked"
    assert payload["blocked_cases"][0]["status"] == "blocked_static_patch"
    assert payload["blocked_cases"][0]["blocker_kind"] == "static_patch_shape_unsupported"
    assert payload["source_apply"] is False


def test_active_application_can_run_without_updating_application_ledger(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "dry-run"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class DryRunError(Exception):\n"
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
                "canonical_project": "dry-run",
                "project_root": "dry-run",
                "path": "pkg.py",
                "class_name": "DryRunError",
                "score": 10,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
            }],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        update_application_ledger=False,
    )

    assert report["status"] == "applied_active_kb"
    assert report["update_application_ledger"] is False
    assert not application_ledger.exists()


def test_active_application_cli_can_write_report_without_updating_ledger(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "probe"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ProbeError(Exception):\n"
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
                "canonical_project": "probe",
                "project_root": "probe",
                "path": "pkg.py",
                "class_name": "ProbeError",
                "score": 10,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
            }],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    tool = Path(__file__).resolve().parents[2] / "tools" / "exception_pickle_active_application.py"

    result = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--root",
            str(tmp_path),
            "--audit",
            str(audit),
            "--transfer-ledger",
            str(ledger),
            "--application-ledger",
            str(application_ledger),
            "--write-report",
            "--summary-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["status"] == "applied_active_kb"
    assert summary["update_application_ledger"] is False
    assert summary["report_path"]
    assert Path(summary["report_path"]).is_file()
    assert not application_ledger.exists()


def test_exception_pickle_active_pattern_negative_controls() -> None:
    recipe = {
        "operator_id": "preserve_exception_constructor_reconstruction",
        "required_constructor_inputs": ["value"],
        "reconstruction_method": "__reduce__",
        "state_strategy": "reuse_direct_assignments",
    }
    with_reduce = (
        "class PayloadError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n"
        "    def __reduce__(self):\n"
        "        return (self.__class__, (self.value,))\n"
    )
    missing_store = (
        "class PayloadError(Exception):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(f'value={value}')\n"
    )
    too_many_inputs = (
        "class PayloadError(Exception):\n"
        "    def __init__(self, a, b, c, d, e):\n"
        "        self.a = a\n"
        "        self.b = b\n"
        "        self.c = c\n"
        "        self.d = d\n"
        "        self.e = e\n"
        "        super().__init__('bad')\n"
    )
    kwonly = (
        "class PayloadError(Exception):\n"
        "    def __init__(self, *, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n"
    )

    assert exception_pickle_reconstruction_patch(with_reduce, class_name="PayloadError", recipe=recipe) is None
    assert exception_pickle_reconstruction_patch(missing_store, class_name="PayloadError", recipe=recipe) is None
    assert exception_pickle_reconstruction_patch(kwonly, class_name="PayloadError", recipe=recipe) is None
    assert exception_pickle_reconstruction_patch(
        too_many_inputs,
        class_name="PayloadError",
        recipe={**recipe, "required_constructor_inputs": ["a", "b", "c", "d", "e"]},
    ) is None


def test_blocked_application_ledger_skips_target_not_whole_project(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "same-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class BlockedError(Exception):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(f'value={value}')\n\n"
        "class AppliedError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "same-project",
                    "project_root": "same-project",
                    "path": "pkg.py",
                    "class_name": "BlockedError",
                    "score": 10,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "same-project",
                    "project_root": "same-project",
                    "path": "pkg.py",
                    "class_name": "AppliedError",
                    "score": 9,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
            ],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"

    first = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution1",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        maximum_attempts=1,
        prioritize_patchable_candidates=False,
    )
    second = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution2",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        maximum_attempts=1,
        prioritize_patchable_candidates=False,
    )

    assert first["status"] == "blocked"
    assert first["attempts"][0]["candidate"]["target"] == "pkg.py:BlockedError.__init__"
    assert second["status"] == "applied_active_kb"
    assert second["selected_application"]["candidate"]["target"] == "pkg.py:AppliedError.__init__"


