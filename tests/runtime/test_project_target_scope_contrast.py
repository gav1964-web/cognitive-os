import json
from pathlib import Path

from runtime.project_target_scope_contrast import evaluate_target_scope_contrasts


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "benchmarks" / "project_target_scope_contrasts_20260830.json"


def test_source_backed_target_scope_contrasts_match_frozen_labels():
    report = evaluate_target_scope_contrasts(root=ROOT, manifest_path=MANIFEST)

    assert report["status"] == "validated"
    assert report["summary"]["case_count"] == 4
    assert report["summary"]["matched_count"] == 4
    assert report["summary"]["source_backed_lineage_count"] == 3
    assert report["summary"]["positive_lineage_count"] == 2
    assert report["summary"]["independent_positive_transfer"] == "passed"
    assert report["capability_effect"] == "no_expansion"
    assert all(result["source_unchanged"] for result in report["results"])


def test_contrast_runner_fails_closed_on_wrong_frozen_label(tmp_path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["cases"] = [manifest["cases"][0]]
    manifest["cases"][0]["expected"]["decision"] = "rejected"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    report = evaluate_target_scope_contrasts(root=ROOT, manifest_path=path)

    assert report["status"] == "failed"
    assert report["results"][0]["matched"] is False
