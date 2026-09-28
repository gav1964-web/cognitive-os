import json
from pathlib import Path

from tools.role_project_type_evaluation import _baseline_sources, _unique_paths


def test_baseline_evaluation_reuses_sources_and_blind_flags(tmp_path: Path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    baseline = tmp_path / "evaluation.json"
    baseline.write_text(
        json.dumps({
            "sources": [
                {"path": first.as_posix(), "blind": False},
                {"path": second.as_posix(), "blind": True},
            ]
        }),
        encoding="utf-8",
    )

    ordinary, blind = _baseline_sources(tmp_path, baseline)

    assert ordinary == [first]
    assert blind == [second]
    assert _unique_paths(tmp_path, [first, second, first]) == [first, second]
