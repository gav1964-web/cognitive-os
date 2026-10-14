from pathlib import Path

from runtime.self_improvement_target_alignment import probe_for_plan, recovery_targets, retrieval_targets


def test_retrieval_targets_keep_best_sample_for_selected_projects():
    report = {
        "selected_projects": ["stateful"],
        "projects": [
            {"project": "stateful", "evidence_samples": [
                {"source": "store.py:update", "score": 100},
                {"source": "store.py:clear", "score": 80},
            ]},
            {"project": "pure", "evidence_samples": [{"source": "text.py:clean"}]},
        ],
    }

    assert retrieval_targets(report) == {"stateful": "store.py:update"}


def test_probe_receives_retrieval_target_and_records_alignment(tmp_path: Path):
    project = tmp_path / "stateful"
    project.mkdir()
    received = {}

    def probe(**kwargs):
        received.update(kwargs)
        return {"baseline": {"selected_extraction_candidate": "store.py:update"}}

    result = probe_for_plan(
        probe, tmp_path, project, 9.7,
        {"retrieval_targets": {"stateful": "store.py:update"}},
    )

    assert received["evaluation_target"] == "store.py:update"
    assert result["retrieval_alignment"] == {
        "mode": "evaluation_only",
        "target": "store.py:update",
        "selected_target": "store.py:update",
        "aligned": True,
    }


def test_probe_without_retrieval_target_preserves_legacy_call(tmp_path: Path):
    project = tmp_path / "plain"
    project.mkdir()

    def probe(**kwargs):
        assert "evaluation_target" not in kwargs
        return {"baseline": {}}

    result = probe_for_plan(probe, tmp_path, project, 9.7, {})

    assert "retrieval_alignment" not in result


def test_recovery_target_is_carried_as_non_scoring_probe_evidence(tmp_path: Path):
    project = tmp_path / "stateful"
    project.mkdir()
    result = probe_for_plan(
        lambda **_kwargs: {"baseline": {}}, tmp_path, project, 9.7,
        {"recovery_targets": {"stateful": [
            "text.py:clean", "text.py:parse", "text.py:render", "text.py:load",
            "text.py:ignored",
        ]}},
    )

    assert result["baseline"]["retrieval_recovery_candidates"] == [
        "text.py:clean", "text.py:parse", "text.py:render", "text.py:load",
    ]


def test_recovery_targets_use_selected_structural_samples():
    report = {
        "selected_projects": ["recoverable"],
        "projects": [{
            "project": "recoverable",
            "recovery_evidence_samples": [{"source": "text.py:clean"}],
        }],
    }

    assert recovery_targets(report) == {"recoverable": ["text.py:clean"]}
