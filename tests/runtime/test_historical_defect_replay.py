from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from runtime.historical_defect_qualification import qualify_historical_defects
from runtime.local_historical_defect_evidence import evidence_digest
from tests.runtime.historical_defect_environment_helpers import environment_bundle
from tests.runtime.test_historical_defect_qualification import _git


def _case(root: Path, baseline: str, fixed: str, test: str) -> tuple[dict, dict]:
    project = root / "project"
    (project / "src" / "sample_pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='sample-pkg'\nversion='1.0'\n", encoding="utf-8")
    source = project / "src" / "sample_pkg" / "__init__.py"
    source.write_text(baseline, encoding="utf-8")
    _git(project, "init", "-q")
    _git(project, "config", "user.name", "Test")
    _git(project, "config", "user.email", "test@example.test")
    _git(project, "remote", "add", "origin", "https://example.test/project.git")
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "baseline")
    revision = _git(project, "rev-parse", "HEAD")
    source.write_text(fixed, encoding="utf-8")
    (project / "tests" / "test_sample.py").write_text(test, encoding="utf-8")
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "fix")
    fix = _git(project, "rev-parse", "HEAD")
    oracle_case = {"candidate_id": "sample", "fix_revision": fix,
                   "test_files": ["tests/test_sample.py"], "test_entry_files": ["tests/test_sample.py"],
                   "production_files": ["src/sample_pkg/__init__.py"]}
    for key, paths in (("test_patch_sha256", oracle_case["test_files"]),
                       ("production_patch_sha256", oracle_case["production_files"])):
        patch = _git(project, "diff", "--no-ext-diff", revision, fix, "--", *paths) + "\n"
        oracle_case[key] = "sha256:" + hashlib.sha256(patch.encode()).hexdigest()
    public = {"schema_version": "local_historical_defect_public_manifest.v1",
              "status": "shortage", "checks": {"selection": True, "minimum_candidates_met": False},
              "cases": [{"candidate_id": "sample", "project_root": "project", "project": "sample",
                         "owner": "owner", "project_stratum": "library_pure_transform",
                         "baseline_revision": revision, "candidate_test_files": ["tests/test_sample.py"],
                         "candidate_test_support_files": ["tests/test_sample.py"]}]}
    public["manifest_digest"] = evidence_digest(public)
    oracle = {"schema_version": "local_historical_defect_oracle.v1", "status": "sealed",
              "public_manifest_digest": public["manifest_digest"], "cases": [oracle_case]}
    oracle["oracle_digest"] = evidence_digest(oracle)
    return public, oracle


def _qualify(root: Path, public: dict, oracle: dict) -> dict:
    return qualify_historical_defects(
        root=root, public=public, oracle=oracle, timeout=60,
        environments=environment_bundle(root, public),
    )["public_receipt"]["cases"][0]


def test_src_layout_repeats_failures_and_verifies_exact_nodes(tmp_path: Path, monkeypatch) -> None:
    public, oracle = _case(tmp_path, "VALUE = 1\n", "VALUE = 2\n",
                           "from sample_pkg import VALUE\ndef test_value():\n    assert VALUE == 2\n")
    monkeypatch.setenv("PYTEST_PLUGINS", "unavailable_global_plugin")
    result = _qualify(tmp_path, public, oracle)

    assert result["status"] == "qualified", result
    assert len(result["baseline_repeats"]) == 2
    assert all(result["comparison_checks"].values())
    assert result["environment_bootstrap"]["kind"] == "isolated_venv"
    assert result["sandbox_cleaned"] and result["source_worktree_unchanged"]


@pytest.mark.parametrize("kind", ["skip", "removed"])
def test_disappearing_failure_does_not_qualify_with_other_passing_tests(tmp_path: Path, kind: str) -> None:
    test = (
        "import pytest\nfrom sample_pkg import VALUE\n"
        "def test_other():\n    assert True\n"
    )
    if kind == "skip":
        test += "@pytest.mark.skipif(VALUE == 2, reason='hidden failure')\ndef test_value():\n    assert VALUE == 2\n"
    else:
        test += "if VALUE == 1:\n    def test_value():\n        assert VALUE == 2\n"
    public, oracle = _case(tmp_path, "VALUE = 1\n", "VALUE = 2\n", test)
    result = _qualify(tmp_path, public, oracle)

    assert result["status"] == "oracle_fix_not_verified", result
    assert result["comparison_checks"]["all_baseline_failures_pass"] is False
    assert result["upstream_fix_confirmed"] is False


def test_unstable_baseline_stops_before_upstream_fix(tmp_path: Path) -> None:
    test = (
        "from pathlib import Path\nfrom sample_pkg import VALUE\n"
        "def test_value():\n    marker=Path(__file__).parent/'seen'\n"
        "    if marker.exists():\n        return\n"
        "    marker.write_text('seen')\n    assert VALUE == 2\n"
    )
    public, oracle = _case(tmp_path, "VALUE = 1\n", "VALUE = 2\n", test)
    result = _qualify(tmp_path, public, oracle)

    assert result["status"] == "not_reproduced", result
    assert result["reason"] == "baseline_failure_not_repeatable"
    assert result["upstream_fix_confirmed"] is False


def test_environment_bundle_drift_is_rejected_before_sandbox(tmp_path: Path, monkeypatch) -> None:
    import runtime.historical_defect_qualification as qualification

    public, oracle = _case(tmp_path, "VALUE=1\n", "VALUE=2\n", "def test_value():\n    assert False\n")
    bundle = environment_bundle(tmp_path, public)
    bundle["public_manifest_digest"] = "changed"
    monkeypatch.setattr(qualification, "qualify_candidate_in_sandbox", lambda **kw: pytest.fail("executed"))

    with pytest.raises(ValueError, match="environment bundle digest mismatch"):
        qualify_historical_defects(root=tmp_path, public=public, oracle=oracle, environments=bundle)
