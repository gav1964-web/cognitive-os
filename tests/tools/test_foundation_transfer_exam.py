from pathlib import Path

import pytest

from tools.foundation_transfer_exam import _freeze_projects, _partition_key, _split_summary


def _repository(path: Path) -> None:
    (path / ".git").mkdir(parents=True)


def test_partition_key_is_seeded_and_stable():
    assert _partition_key("seed", "Owner/Repo") == _partition_key("seed", "owner/repo")
    assert _partition_key("seed", "owner/repo") != _partition_key("other", "owner/repo")


def test_freeze_projects_is_stratified_and_records_commits(tmp_path, monkeypatch):
    selection = {"projects": [
        {"full_name": f"owner/{stratum}-repo-{index}", "stratum": stratum}
        for stratum in ("api", "cli") for index in range(4)
    ]}
    for row in selection["projects"]:
        _repository(tmp_path / "src" / row["full_name"].replace("/", "__"))
    monkeypatch.setattr("tools.foundation_transfer_exam._git_output", lambda *_args: "head")

    projects = _freeze_projects(tmp_path, selection, "seed", 1)
    summary = _split_summary(projects)

    assert summary == {
        "project_count": 8, "train_count": 6, "holdout_count": 2,
        "strata": ["api", "cli"],
    }
    assert {row["commit"] for row in projects} == {"head"}


def test_freeze_projects_rejects_empty_training_partition(tmp_path):
    selection = {"projects": [{"full_name": "owner/only", "stratum": "api"}]}

    with pytest.raises(ValueError, match="invalid holdout size"):
        _freeze_projects(tmp_path, selection, "seed", 1)
