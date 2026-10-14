"""Root test modules remain test evidence, never production repair oracles."""
from pathlib import Path

import pytest

import runtime.local_historical_defect_mining as mining
from runtime.project_native_failure_pytest import _native_pytest_targets
from tests.runtime.test_local_historical_defect_mining import _policy, _workspace


@pytest.mark.parametrize("test_path", ["test.py", "parser_test.py", "test_parser.py"])
@pytest.mark.parametrize("production_changed", [False, True])
def test_root_test_delta_is_separate_from_production(
    tmp_path: Path, monkeypatch, test_path: str, production_changed: bool,
) -> None:
    _workspace(tmp_path)
    monkeypatch.setattr(mining, "_git_snapshot", lambda project: {
        "status": "", "revision": "f" * 40,
        "origin": f"https://example.test/{project.name}.git",
        "shallow": "false", "history_count": "2",
    })
    delta = ("M\tsrc/core.py\n" if production_changed else "") + f"M\t{test_path}\n"
    monkeypatch.setattr(mining, "_git", lambda project, args, **kwargs: (
        f"{'2' * 40}\x1f{'1' * 40}\x1ffix bug\n" if args[0] == "log" else
        delta if args[0] == "diff-tree" else "patch"
    ))
    result = mining.mine_historical_defect_candidates(root=tmp_path, policy=_policy())
    public = result["public_manifest"]
    assert bool(public["cases"]) is production_changed
    for case in public["cases"]:
        assert case["candidate_test_files"] == [test_path]
        assert "fix_revision" not in case
    for oracle in result["oracle_manifest"]["cases"]:
        assert oracle["production_files"] == ["src/core.py"]
        assert oracle["test_files"] == [test_path]


@pytest.mark.parametrize("names", [["test.py"], ["tests.py"], ["tests.py", "test.py"]])
def test_legacy_root_suite_is_not_lost_at_native_regression(tmp_path, names):
    for name in names:
        (tmp_path / name).write_text("def test_one(): assert False\n", encoding="utf-8")
    assert _native_pytest_targets(tmp_path, None) == names
    assert _native_pytest_targets(tmp_path, [names[0] + "::test_one"]) == [names[0] + "::test_one"]
