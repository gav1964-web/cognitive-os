from __future__ import annotations

from runtime.corpus_evaluation_factory import build_corpus_evaluation_plan


def _row(index: int, project_type: str, *, exposure: str = "untouched", markers=None):
    return {
        "project": f"project-{project_type}-{index}",
        "project_type": project_type,
        "source_lineage": f"owner-{project_type}-{index}",
        "content_digest": "sha256:" + f"{index + (100 if project_type == 'library_pure_transform' else 0):064x}",
        "exposure": exposure,
        "markers": markers or [],
        "path": f"artifacts/corpus/{project_type}/{index}",
    }


def test_existing_corpus_is_split_before_network_fallback():
    records = [
        _row(index, project_type)
        for project_type in ("cli_local_tool", "library_pure_transform")
        for index in range(1, 6)
    ]

    report = build_corpus_evaluation_plan(records)

    assert report["status"] == "local_corpus_sufficient"
    assert report["network_fallback"]["allowed"] is False
    assert all(len(row["holdout"]) == 2 for row in report["splits"])
    assert all(len(row["acquisition"]) == 3 for row in report["splits"])
    assert all(row["checks"]["lineage_disjoint"] for row in report["splits"])


def test_network_fallback_is_allowed_only_for_measured_shortage():
    report = build_corpus_evaluation_plan([_row(1, "cli_local_tool")])

    assert report["status"] == "local_corpus_shortage"
    assert report["network_fallback"] == {
        "allowed": True,
        "reason": "local_corpus_shortage",
    }


def test_exposed_and_duplicate_projects_do_not_enter_splits():
    records = [_row(index, "cli_local_tool") for index in range(1, 6)]
    records.append({**records[0], "project": "duplicate-copy"})
    records.append(_row(9, "cli_local_tool", exposure="historically_exposed"))

    report = build_corpus_evaluation_plan(records)
    selected = [project["project"] for split in report["splits"] for key in ("holdout", "acquisition") for project in split[key]]

    assert len({"duplicate-copy", "project-cli_local_tool-1"}.intersection(selected)) == 1
    assert "project-cli_local_tool-9" not in selected


def test_unknown_cluster_needs_projects_lineages_digests_and_markers():
    records = [
        _row(index, "unknown_new_archetype", markers=["event-log", "projection"])
        for index in range(1, 4)
    ]

    report = build_corpus_evaluation_plan(records)

    assert report["unknown_clusters"][0]["status"] == "research_candidate"
    assert report["unknown_clusters"][0]["automatic_promotion"] is False


def test_one_lineage_unknown_cluster_stays_quarantined():
    records = [
        {**_row(index, "unknown_new_archetype", markers=["event-log", "projection"]), "source_lineage": "same-owner"}
        for index in range(1, 4)
    ]

    report = build_corpus_evaluation_plan(records)

    assert report["unknown_clusters"][0]["status"] == "collect_more_cases"
    assert report["unknown_clusters"][0]["checks"]["minimum_lineages"] is False
