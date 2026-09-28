from __future__ import annotations

import json

from runtime.evaluation_corpus import ensure_evaluation_corpus
from tools.evaluation_check import check_evaluation


def test_evaluation_corpus_seeds_contract_tasks(tmp_path):
    report = ensure_evaluation_corpus(root=tmp_path, count=3, write=True)

    assert report["artifact_type"] == "EvaluationCorpusSeedReport"
    assert report["created_count"] == 3
    assert (tmp_path / "evaluation" / "task11_image_contents_cli" / "prompt.md").is_file()
    metrics = json.loads((tmp_path / "evaluation" / "task11_image_contents_cli" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["invariants"]["teacher_reference_is_ground_truth"] is False
    assert check_evaluation(tmp_path)["ok"] is True
