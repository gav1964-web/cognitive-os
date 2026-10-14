from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from cognitive_replay import qualify_candidate_in_sandbox
from cognitive_replay.evidence import evidence_digest
from cognitive_replay.git import _git as read_git

def _git(project, *args):
    return read_git(project, list(args)).strip()

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

@pytest.mark.parametrize("fixed, expected", [("return x.strip().lower()", "qualified"),
                                           ("return x.strip()", "oracle_fix_not_verified")])
def test_installed_api_replays_real_git_defect(tmp_path, profile_factory, fixed, expected):
    public, oracle = _case(
        tmp_path, "def normalize(x): return x\n", f"def normalize(x): {fixed}\n",
        "from sample_pkg import normalize\ndef test_normalize(): assert normalize(' A ') == 'a'\n",
    )
    result = qualify_candidate_in_sandbox(
        root=tmp_path, public=public["cases"][0], oracle=oracle["cases"][0],
        environment_profile=profile_factory(tmp_path), timeout=60,
    )
    assert result["status"] == expected, result
    assert len(result["baseline_repeats"]) == 2
    assert result["source_head_unchanged"]
    assert result["source_worktree_unchanged"]
    assert result["source_worktree_registry_unchanged"]
    assert result["sandbox_cleaned"]
    assert result["comparison_checks"]["collection_unchanged"]
    assert result["comparison_checks"]["fixed_suite_passed"] == (expected == "qualified")
