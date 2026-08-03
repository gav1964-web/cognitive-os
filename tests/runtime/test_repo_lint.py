from __future__ import annotations

from pathlib import Path

import pytest

from runtime.repo_lint import RepoLintError, assert_repository_lint, lint_repository


def test_repo_lint_rejects_python_file_over_limit(tmp_path: Path):
    source = tmp_path / "runtime" / "large.py"
    source.parent.mkdir()
    source.write_text("\n".join(["x = 1"] * 401), encoding="utf-8")

    violations = lint_repository(tmp_path)

    assert violations[0].path == "runtime/large.py"
    assert violations[0].line_count == 401
    with pytest.raises(RepoLintError, match="exceed 400"):
        assert_repository_lint(tmp_path)


def test_repo_lint_ignores_machine_artifacts(tmp_path: Path):
    artifact = tmp_path / "artifacts" / "large.py"
    artifact.parent.mkdir()
    artifact.write_text("\n".join(["x = 1"] * 999), encoding="utf-8")

    assert lint_repository(tmp_path) == []


def test_repo_lint_does_not_recurse_into_artifact_subtrees(tmp_path: Path):
    artifact = tmp_path / "artifacts" / "github" / "src" / "repo" / "pkg"
    artifact.mkdir(parents=True)
    (artifact / "large.py").write_text("\n".join(["x = 1"] * 999), encoding="utf-8")
    source = tmp_path / "runtime" / "small.py"
    source.parent.mkdir()
    source.write_text("x = 1\n", encoding="utf-8")

    assert lint_repository(tmp_path) == []
