from __future__ import annotations

from pathlib import Path

import pytest

from runtime.repo_lint import RepoLintError, assert_repository_lint, lint_repository
from runtime.repo_lint import size_warnings


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


@pytest.mark.parametrize("directory", [".pytest-tmp-run", ".nfi", ".nft", ".pde"])
def test_repo_lint_ignores_machine_local_test_directories(tmp_path: Path, directory: str):
    source = tmp_path / directory / "nested" / "large.py"
    source.parent.mkdir(parents=True)
    source.write_text("\n".join(["x = 1"] * 999), encoding="utf-8")

    assert lint_repository(tmp_path) == []


@pytest.mark.parametrize("directory", ["evaluation", "benchmarks/owned", "curricula/owned", "runtime/generated", "generated/specs"])
def test_maintained_sources_are_not_hidden_by_broad_exclusions(tmp_path, directory):
    source = tmp_path / directory / "large.py"
    source.parent.mkdir(parents=True)
    source.write_text("pass\n" * 401, encoding="utf-8")
    assert len(lint_repository(tmp_path)) == 1


@pytest.mark.parametrize("directory", ["benchmarks/github_trial/src", "curricula/demo_external_local_3", ".venv/Lib", "generated/cache"])
def test_external_and_generated_sources_are_excluded(tmp_path, directory):
    source = tmp_path / directory / "large.py"
    source.parent.mkdir(parents=True)
    source.write_text("pass\n" * 401, encoding="utf-8")
    assert lint_repository(tmp_path) == []


def test_warning_is_advisory_and_hard_limit_counts_blank_lines(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("\n" * 350, encoding="utf-8")
    assert lint_repository(tmp_path) == []
    assert size_warnings(tmp_path)[0].line_count == 350
    source.write_text("\n" * 401, encoding="utf-8")
    assert lint_repository(tmp_path)[0].line_count == 401
    assert size_warnings(tmp_path) == []
