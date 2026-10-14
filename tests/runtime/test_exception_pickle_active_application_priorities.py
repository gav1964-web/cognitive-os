from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_prioritizes_precheck_eligible_candidate(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "pkg.py").write_text(
        "class NotReplayableError(Exception):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    applied = tmp_path / "applied"
    applied.mkdir()
    (applied / "pkg.py").write_text(
        "class ReplayableError(Exception):\n"
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
                    "canonical_project": "blocked",
                    "project_root": "blocked",
                    "path": "pkg.py",
                    "class_name": "NotReplayableError",
                    "score": 100,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": [],
                },
                {
                    "canonical_project": "applied",
                    "project_root": "applied",
                    "path": "pkg.py",
                    "class_name": "ReplayableError",
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
    assert report["selected_application"]["candidate"]["project"] == "applied"


def test_active_application_limits_repeated_static_patch_blockers_per_project(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "pkg.py").write_text(
        "class BadOne(Exception):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(value)\n\n"
        "class BadTwo(Exception):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    good = tmp_path / "good"
    good.mkdir()
    (good / "pkg.py").write_text(
        "class GoodError(Exception):\n"
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
                    "canonical_project": "bad",
                    "project_root": "bad",
                    "path": "pkg.py",
                    "class_name": "BadOne",
                    "score": 100,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "bad",
                    "project_root": "bad",
                    "path": "pkg.py",
                    "class_name": "BadTwo",
                    "score": 99,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "good",
                    "project_root": "good",
                    "path": "pkg.py",
                    "class_name": "GoodError",
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
        maximum_attempts=3,
        maximum_static_patch_blockers_per_project=1,
        prioritize_patchable_candidates=False,
    )

    assert report["status"] == "applied_active_kb"
    assert report["attempt_count"] == 2
    assert report["skipped_candidate_count"] == 1
    assert report["attempts"][0]["candidate"]["target"] == "pkg.py:BadOne.__init__"
    assert report["selected_application"]["candidate"]["project"] == "good"
    assert report["skipped_candidates"][0]["target"] == "pkg.py:BadTwo.__init__"


def test_active_application_prioritizes_patchable_candidate(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "pkg.py").write_text(
        "class NotPatchableError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    applied = tmp_path / "applied"
    applied.mkdir()
    (applied / "pkg.py").write_text(
        "class PatchableError(Exception):\n"
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
                    "canonical_project": "blocked",
                    "project_root": "blocked",
                    "path": "pkg.py",
                    "class_name": "NotPatchableError",
                    "score": 100,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "applied",
                    "project_root": "applied",
                    "path": "pkg.py",
                    "class_name": "PatchableError",
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
    assert report["selected_application"]["candidate"]["project"] == "applied"


def test_active_application_limits_repeated_replay_blockers_per_project(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    dep = tmp_path / "dep"
    dep.mkdir()
    (dep / "pkg.py").write_text(
        "import missing_dependency_for_replay\n\n"
        "class DepOne(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n\n"
        "class DepTwo(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    good = tmp_path / "good"
    good.mkdir()
    (good / "pkg.py").write_text(
        "class GoodError(Exception):\n"
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
                    "canonical_project": "dep",
                    "project_root": "dep",
                    "path": "pkg.py",
                    "class_name": "DepOne",
                    "score": 100,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "dep",
                    "project_root": "dep",
                    "path": "pkg.py",
                    "class_name": "DepTwo",
                    "score": 99,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "good",
                    "project_root": "good",
                    "path": "pkg.py",
                    "class_name": "GoodError",
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
        maximum_attempts=3,
        maximum_replay_blockers_per_project=1,
        prioritize_patchable_candidates=False,
        prioritize_dependency_light_candidates=False,
        allow_target_import_stubs=False,
    )

    assert report["status"] == "applied_active_kb"
    assert report["attempt_count"] == 2
    assert report["skipped_candidate_count"] == 1
    assert report["attempts"][0]["candidate"]["target"] == "pkg.py:DepOne.__init__"
    assert report["selected_application"]["candidate"]["project"] == "good"
    assert report["skipped_candidates"][0]["target"] == "pkg.py:DepTwo.__init__"
