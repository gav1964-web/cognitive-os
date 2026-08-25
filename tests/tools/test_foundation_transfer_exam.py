import json
from pathlib import Path

import pytest

from tools.foundation_transfer_checkpoint import checkpoint_path
from tools.foundation_transfer_exam import (
    _freeze_projects, _partition_key, _split_summary, run_exam,
)


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


def _exam_manifest(corpus: Path) -> None:
    (corpus / "src/train").mkdir(parents=True)
    (corpus / "src/holdout").mkdir(parents=True)
    (corpus / "transfer_exam.json").write_text(json.dumps({
        "status": "frozen", "engine_fingerprint": "engine",
        "promotion_snapshot_sha256": "snapshot",
        "projects": [
            {"full_name": "owner/train", "path": "src/train", "commit": "a", "partition": "train"},
            {"full_name": "owner/holdout", "path": "src/holdout", "commit": "b", "partition": "holdout"},
        ],
    }), encoding="utf-8")


def _report(root: Path, name: str, project: str = "holdout") -> dict:
    report = {
        "status": "ok", "summary": {"project_min_score": 9.7},
        "cases": [{"project": project, "status": "ok", "project_min_score": 9.7}],
    }
    path = root / f"{name}.json"
    report["report_path"] = path.as_posix()
    path.write_text(json.dumps(report), encoding="utf-8")
    return report


def test_exam_resumes_after_interrupted_final_holdout_without_retraining(
    tmp_path, monkeypatch,
):
    corpus = tmp_path / "corpus"
    _exam_manifest(corpus)
    monkeypatch.setattr("tools.foundation_transfer_exam._verify_frozen_state", lambda *_args: None)
    measurements = []

    def measure(root, projects, _target):
        measurements.append([path.name for path in projects])
        if len(measurements) == 3:
            raise KeyboardInterrupt()
        return _report(root, f"measure-{len(measurements)}", projects[0].name)

    training_calls = []

    def trainer(**_kwargs):
        training_calls.append(True)
        return _report(tmp_path, "training", "train")

    monkeypatch.setattr("tools.foundation_transfer_exam._measure", measure)
    with pytest.raises(KeyboardInterrupt):
        run_exam(
            tmp_path, corpus, target_score=9.7, max_training_projects=1,
            max_iterations=1, trainer=trainer,
        )

    checkpoint = json.loads(checkpoint_path(corpus).read_text(encoding="utf-8"))
    assert checkpoint["stage"] == "training_completed"
    assert checkpoint["resume_allowed"] is True

    result = run_exam(
        tmp_path, corpus, target_score=9.7, max_training_projects=1,
        max_iterations=1,
        trainer=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not retrain")),
        resume=True,
    )

    assert result["status"] == "transfer_verified"
    assert len(training_calls) == 1
    assert measurements == [["train"], ["holdout"], ["holdout"], ["holdout"]]
    assert not checkpoint_path(corpus).exists()


def test_training_interruption_rolls_back_and_blocks_resume(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    _exam_manifest(corpus)
    monkeypatch.setattr("tools.foundation_transfer_exam._verify_frozen_state", lambda *_args: None)
    monkeypatch.setattr(
        "tools.foundation_transfer_exam._measure",
        lambda root, projects, _target: _report(root, f"measure-{projects[0].name}", projects[0].name),
    )
    rollbacks = []
    monkeypatch.setattr(
        "tools.foundation_transfer_exam.rollback_promotion_state",
        lambda root, snapshot: rollbacks.append((root, snapshot)) or [],
    )

    with pytest.raises(KeyboardInterrupt):
        run_exam(
            tmp_path, corpus, target_score=9.7, max_training_projects=1,
            max_iterations=1,
            trainer=lambda **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

    checkpoint = json.loads(checkpoint_path(corpus).read_text(encoding="utf-8"))
    assert checkpoint["stage"] == "training_interrupted"
    assert checkpoint["resume_allowed"] is False
    assert checkpoint["reason"] == "training_stage_interrupted_restart_required"
    assert len(rollbacks) == 1
