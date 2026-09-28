from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import runtime.historical_defect_qualification as qualification
from runtime.historical_defect_sandbox import _pytest_status
from runtime.local_historical_defect_evidence import evidence_digest
from tests.runtime.historical_defect_environment_helpers import environment_bundle


def _git(project: Path, *args: str) -> str:
    run = subprocess.run(
        ["git", "-C", str(project), *args], capture_output=True,
        text=True, check=True, shell=False,
    )
    return run.stdout.strip()


def _candidate(root: Path, name: str, project_type: str) -> tuple[dict, dict]:
    project = root / name
    (project / "tests").mkdir(parents=True)
    (project / "calc.py").write_text("def add_one(value):\n    return value - 1\n", encoding="utf-8")
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.test")
    _git(project, "config", "user.name", "Test")
    _git(project, "remote", "add", "origin", f"https://github.com/{name}/project.git")
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    baseline = _git(project, "rev-parse", "HEAD")
    (project / "calc.py").write_text("def add_one(value):\n    return value + 1\n", encoding="utf-8")
    (project / "tests" / "test_calc.py").write_text(
        "from calc import add_one\n\ndef test_add_one():\n    assert add_one(1) == 2\n",
        encoding="utf-8",
    )
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "fix calculation")
    fix = _git(project, "rev-parse", "HEAD")
    test_patch = _git(project, "diff", "--no-ext-diff", baseline, fix, "--", "tests/test_calc.py") + "\n"
    source_patch = _git(project, "diff", "--no-ext-diff", baseline, fix, "--", "calc.py") + "\n"
    candidate_id = hashlib.sha256(name.encode()).hexdigest()[:20]
    public = {
        "candidate_id": candidate_id, "project": name,
        "project_stratum": project_type, "owner": name,
        "project_root": project.relative_to(root).as_posix(),
        "baseline_revision": baseline,
        "candidate_test_files": ["tests/test_calc.py"],
        "candidate_test_support_files": ["tests/test_calc.py"],
    }
    oracle = {
        "candidate_id": candidate_id, "fix_revision": fix,
        "production_files": ["calc.py"], "test_files": ["tests/test_calc.py"],
        "test_entry_files": ["tests/test_calc.py"],
        "test_patch_sha256": "sha256:" + hashlib.sha256(test_patch.encode()).hexdigest(),
        "production_patch_sha256": "sha256:" + hashlib.sha256(source_patch.encode()).hexdigest(),
    }
    return public, oracle


def _manifests(root: Path) -> tuple[dict, dict]:
    pairs = [
        _candidate(root, f"owner-{index}", project_type)
        for index, project_type in enumerate((
            "cli_local_tool", "cli_local_tool",
            "library_pure_transform", "library_pure_transform",
        ), start=1)
    ]
    public = {
        "schema_version": "local_historical_defect_public_manifest.v1",
        "status": "ready", "checks": {"selection": True},
        "cases": [row[0] for row in pairs],
    }
    public["manifest_digest"] = evidence_digest(public)
    oracle = {
        "schema_version": "local_historical_defect_oracle.v1",
        "status": "sealed", "public_manifest_digest": public["manifest_digest"],
        "cases": [row[1] for row in pairs],
    }
    oracle["oracle_digest"] = evidence_digest(oracle)
    return public, oracle


def test_qualification_proves_failure_and_fix_without_mutating_sources(tmp_path: Path) -> None:
    public, oracle = _manifests(tmp_path)

    result = qualification.qualify_historical_defects(
        root=tmp_path, public=public, oracle=oracle, timeout=60,
        environments=environment_bundle(tmp_path, public),
    )

    receipt = result["public_receipt"]
    assert receipt["status"] == "ready_for_role_evaluation", receipt
    assert receipt["summary"]["qualified_counts"] == {
        "cli_local_tool": 2, "library_pure_transform": 2,
    }
    assert all(row["baseline"]["status"] == "reproducible_failure" for row in receipt["cases"])
    assert all(row["upstream_fix_confirmed"] for row in receipt["cases"])
    assert all("fix_revision" not in row for row in receipt["cases"])
    assert all(_git(tmp_path / row["project"], "status", "--porcelain") == "" for row in receipt["cases"])


def test_qualification_rejects_public_manifest_digest_drift(tmp_path: Path) -> None:
    public, oracle = _manifests(tmp_path)
    public["cases"][0]["baseline_revision"] = "0" * 40

    try:
        qualification.qualify_historical_defects(root=tmp_path, public=public, oracle=oracle)
    except qualification.HistoricalDefectQualificationError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("drifted manifest was accepted")


def test_qualification_accepts_safe_partial_shortage_campaign(tmp_path: Path) -> None:
    public, oracle = _manifests(tmp_path)
    public["status"] = "shortage"
    public["checks"] = {"selection": True, "minimum_candidates_met": False}
    public["cases"] = public["cases"][:2]
    public["manifest_digest"] = evidence_digest({
        key: value for key, value in public.items() if key != "manifest_digest"
    })
    oracle["public_manifest_digest"] = public["manifest_digest"]
    oracle["cases"] = oracle["cases"][:2]
    oracle["oracle_digest"] = evidence_digest({
        key: value for key, value in oracle.items() if key != "oracle_digest"
    })

    result = qualification.qualify_historical_defects(
        root=tmp_path, public=public, oracle=oracle, timeout=60,
        environments=environment_bundle(tmp_path, public),
    )

    receipt = result["public_receipt"]
    assert receipt["status"] == "insufficient_qualified_defects"
    assert receipt["summary"]["qualified_counts"] == {
        "cli_local_tool": 2, "library_pure_transform": 0,
    }
    assert receipt["checks"]["two_qualified_per_type"] is False


def test_missing_runtime_dependency_is_environment_blocked() -> None:
    run = {
        "returncode": 1,
        "stdout": "FAILED test_case.py::test_case\n1 failed",
        "stderr": "ModuleNotFoundError: No module named 'optional_dependency'",
    }

    assert _pytest_status(run) == "environment_blocked"


def _validation_manifests() -> tuple[dict, dict]:
    public = {
        "schema_version": "local_historical_defect_public_manifest.v1",
        "status": "ready", "checks": {"selection": True},
        "cases": [
            {"candidate_id": str(index), "project_stratum": project_type,
             "owner": f"owner-{index}", "project_root": f"projects/{index}"}
            for index, project_type in enumerate((
                "cli_local_tool", "cli_local_tool",
                "library_pure_transform", "library_pure_transform",
            ))
        ],
    }
    oracle = {
        "schema_version": "local_historical_defect_oracle.v1", "status": "sealed",
        "cases": [{"candidate_id": str(index), "fix_revision": "f" * 40} for index in range(4)],
    }
    _seal(public, oracle)
    return public, oracle


def _seal(public: dict, oracle: dict) -> None:
    public["manifest_digest"] = evidence_digest({
        key: value for key, value in public.items() if key != "manifest_digest"
    })
    oracle["public_manifest_digest"] = public["manifest_digest"]
    oracle["oracle_digest"] = evidence_digest({
        key: value for key, value in oracle.items() if key != "oracle_digest"
    })


@pytest.mark.parametrize("mutation", ["missing_digest", "fix_revision", "patch_digest"])
def test_qualification_rejects_unbound_oracle_before_execution(
    tmp_path: Path, monkeypatch, mutation: str,
) -> None:
    public, oracle = _validation_manifests()
    if mutation == "missing_digest":
        oracle.pop("oracle_digest")
    else:
        field = "fix_revision" if mutation == "fix_revision" else "production_patch_sha256"
        oracle["cases"][0][field] = "changed"
    monkeypatch.setattr(qualification, "qualify_candidate_in_sandbox", lambda **kw: pytest.fail("executed"))

    with pytest.raises(qualification.HistoricalDefectQualificationError, match="oracle digest mismatch"):
        qualification.qualify_historical_defects(root=tmp_path, public=public, oracle=oracle)


@pytest.mark.parametrize("mutation", [
    "public_duplicate", "oracle_duplicate", "owner", "project", "project_alias",
])
def test_qualification_rejects_reused_candidates_before_execution(
    tmp_path: Path, monkeypatch, mutation: str,
) -> None:
    public, oracle = _validation_manifests()
    if mutation.endswith("duplicate"):
        manifest = public if mutation == "public_duplicate" else oracle
        manifest["cases"].append(dict(manifest["cases"][0]))
    else:
        field = "owner" if mutation == "owner" else "project_root"
        public["cases"][1][field] = public["cases"][0][field]
        if mutation == "project_alias":
            public["cases"][1][field] += "/."
    _seal(public, oracle)
    monkeypatch.setattr(qualification, "qualify_candidate_in_sandbox", lambda **kw: pytest.fail("executed"))

    with pytest.raises(qualification.HistoricalDefectQualificationError, match="unique|independent"):
        qualification.qualify_historical_defects(root=tmp_path, public=public, oracle=oracle)


@pytest.mark.parametrize("output", ["2 skipped in 0.01s", "1 xfailed in 0.01s", ""])
def test_zero_exit_without_passing_tests_is_not_verification(output: str) -> None:
    assert _pytest_status({"returncode": 0, "stdout": output, "structured": {
        "status": "valid", "passed": [], "failed": [], "errors": [], "collection_errors": [],
    }}) == "no_tests_executed"


def test_qualification_preserves_unrelated_prunable_worktree(tmp_path: Path) -> None:
    case, sealed = _candidate(tmp_path, "owner-cleanup", "cli_local_tool")
    source = tmp_path / case["project"]
    stale = tmp_path / "unrelated-worktree"
    _git(source, "worktree", "add", "--detach", str(stale), case["baseline_revision"])
    (stale / ".git").unlink()
    (stale / "calc.py").unlink()
    stale.rmdir()
    before = _git(source, "worktree", "list", "--porcelain")
    assert "prunable" in before
    public, oracle = _validation_manifests()
    public.update(status="shortage", cases=[case])
    oracle["cases"] = [sealed]
    _seal(public, oracle)

    result = qualification.qualify_historical_defects(
        root=tmp_path, public=public, oracle=oracle, timeout=60,
        environments=environment_bundle(tmp_path, public),
    )

    receipt = result["public_receipt"]
    assert receipt["cases"][0]["status"] == "qualified", receipt
    assert receipt["checks"]["source_worktree_registries_unchanged"] is True
    assert receipt["checks"]["sandboxes_cleaned"] is True
    assert _git(source, "worktree", "list", "--porcelain") == before
