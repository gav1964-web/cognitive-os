from pathlib import Path

import runtime.project_corpus_qualification as qualification


def _analysis(kind: str, confidence: float = 0.8):
    return {
        "project_map_report": {
            "answers": {
                "1_scope": {"domain_profile": {"kind": kind, "confidence": confidence, "evidence": [kind]}},
                "2_execution": {"central_flow_nodes": [{"side_effects": ["filesystem"]}]},
            },
            "source_health": {"project_shape": "single_project"},
        }
    }


def test_corpus_qualification_separates_matches_reviews_and_rejections(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    for name in ("docs", "weak", "library", "foreign"):
        (projects / name).mkdir(parents=True)

    monkeypatch.setattr(
        qualification,
        "_primary_language_scope",
        lambda path: {"status": "out_of_scope" if path.name == "foreign" else "in_scope"},
    )
    analyses = {
        "docs": _analysis("docs_site_generator"),
        "weak": _analysis("docs_site_generator", 0.6),
        "library": _analysis("schema_validation_library"),
    }
    monkeypatch.setattr(
        qualification,
        "analyze_role_project",
        lambda *, project_dir, **_: analyses[project_dir.name],
    )

    report = qualification.qualify_project_corpus(
        root=Path(tmp_path),
        projects_dir=projects,
        expected_stratum="framework_plugin_build",
        minimum_qualified=1,
    )

    statuses = {case["project"]: case["qualification_status"] for case in report["cases"]}
    assert statuses == {
        "docs": "qualified",
        "foreign": "rejected",
        "library": "rejected",
        "weak": "needs_review",
    }
    assert report["summary"] == {"qualified": 1, "needs_review": 1, "rejected": 2}
    assert report["status"] == "ready"
    assert report["qualified_projects"] == ["docs"]
    assert report["replacement_count"] == 0
