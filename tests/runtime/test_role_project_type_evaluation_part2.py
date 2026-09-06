from __future__ import annotations

from tests.runtime.role_project_type_evaluation_helpers import *

def test_legacy_component_score_cannot_claim_maturity(tmp_path: Path) -> None:
    source = tmp_path / "legacy.json"
    source.write_text(
        json.dumps({
            "cases": [
                    {
                        "project": f"worker-{index}",
                        "project_classification": {
                            "schema_version": "role_project_classification.v1",
                            "policy_version": load_role_project_type_policy()["classification_version"],
                            "project_stratum": "async_worker_scheduler",
                        },
                    "score": {"implementation_score": 1.0, "qa_score": 1.0},
                }
                for index in range(5)
            ]
        }),
        encoding="utf-8",
    )

    report = build_role_project_type_evaluation(
        root=tmp_path,
        report_paths=[source, source],
        blind_report_paths=[source],
    )

    implementer = _cell(report, "implementer", "async_worker_scheduler")
    assert implementer["score"] == 8.9
    assert implementer["maturity"] == "usable"
    assert implementer["score_sources"] == ["legacy_component_score"]


def test_markdown_renders_heatmap_and_priority_queue(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text(json.dumps({"cases": [_case("cli", 8.5, 7.0)]}), encoding="utf-8")
    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[source])

    rendered = render_role_project_type_markdown(report)

    assert "| Project stratum |" in rendered
    assert "implementer x cli_local_tool" in rendered


def test_unknown_stratum_cannot_become_mature(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps({"cases": [_unknown_case(f"a-{i}") for i in range(3)]}), encoding="utf-8")
    second.write_text(json.dumps({"cases": [_unknown_case(f"b-{i}") for i in range(3)]}), encoding="utf-8")

    report = build_role_project_type_evaluation(
        root=tmp_path,
        report_paths=[first, second],
        blind_report_paths=[first, second],
    )

    cell = _cell(report, "project_analyzer", "unknown_new_archetype")
    assert cell["score"] == 10.0
    assert cell["maturity"] == "usable"
    assert "unclassified_archetype" in cell["evidence_gaps"]
    assert report["maturity_status"] == "needs_work"
    assert report["summary"]["classification_debt_count"] == 6
    assert report["classification_debt"]["status"] == "needs_classification"
    assert {row["project"] for row in report["classification_debt"]["items"]} == {
        *(f"a-{index}" for index in range(3)),
        *(f"b-{index}" for index in range(3)),
    }
    assert report["classification_debt"]["items"][0]["observed_roles"] == ["project_analyzer"]
    lifecycle = report["unknown_project_lifecycle"]
    assert lifecycle["status"] == "research_required"
    assert lifecycle["intake_count"] == 6
    assert lifecycle["provisional_candidate_count"] == 0
    assert all(row["routing"]["downstream_roles_blocked"] for row in lifecycle["intakes"])
    assert lifecycle["policy"]["automatic_stratum_creation_forbidden"] is True
    assert _cell(report, "researcher", "unknown_new_archetype")["applicable"] is True
    assert _cell(report, "architect", "unknown_new_archetype")["maturity"] == "not_applicable"
    assert "## Classification debt" in render_role_project_type_markdown(report)
    assert "## Unknown project lifecycle" in render_role_project_type_markdown(report)


def test_unknown_hypothesis_stays_provisional_without_confirmed_evidence(tmp_path: Path) -> None:
    source = tmp_path / "unknown.json"
    case = _unknown_case("novel-one")
    case["unknown_archetype_evidence"] = {
        "hypothesis_id": "event_sourced_projection",
        "label": "Event-sourced projection",
        "candidate_markers": ["event log", "projection"],
        "confidence": 0.9,
        "status": "observed",
    }
    source.write_text(json.dumps({"cases": [case]}), encoding="utf-8")

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[source])

    lifecycle = report["unknown_project_lifecycle"]
    provisional = lifecycle["provisional_candidates"][0]
    assert lifecycle["status"] == "provisional_candidates"
    assert lifecycle["intakes"][0]["status"] == "provisional"
    assert provisional["confirmed_project_count"] == 0
    assert provisional["status"] == "collect_more_cases"
    assert provisional["promotion_gate"]["automatic_promotion"] is False


def test_repeated_source_backed_unknown_hypothesis_reaches_manual_review_gate(tmp_path: Path) -> None:
    sources = []
    for index in range(3):
        source = tmp_path / f"unknown-{index}.json"
        case = _unknown_case(f"novel-{index}")
        case["unknown_archetype_evidence"] = {
            "hypothesis_id": "event_sourced_projection",
            "label": "Event-sourced projection",
            "candidate_markers": ["event log", "projection"],
            "first_slice_hint": "append_and_rebuild_projection",
            "confidence": 0.85,
            "status": "confirmed",
            "source_lineage": f"owner-{index % 2}",
            "source_digests": [{"evidence_hash": f"digest-{index}", "confidence": 0.85}],
        }
        source.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
        sources.append(source)

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=sources)

    provisional = report["unknown_project_lifecycle"]["provisional_candidates"][0]
    assert provisional["confirmed_project_count"] == 3
    assert provisional["status"] == "needs_teacher_approval"
    assert provisional["promotion_gate"]["next_action"] == "request_external_teacher_review"
    assert provisional["candidate"]["evidence_policy"]["automatic_self_promotion_forbidden"] is True


def test_unknown_hypothesis_from_one_lineage_cannot_reach_review_gate(tmp_path: Path) -> None:
    sources = []
    for index in range(3):
        source = tmp_path / f"same-owner-{index}.json"
        case = _unknown_case(f"novel-{index}")
        case["unknown_archetype_evidence"] = {
            "hypothesis_id": "event_sourced_projection",
            "label": "Event-sourced projection",
            "candidate_markers": ["event log", "projection"],
            "confidence": 0.9,
            "status": "confirmed",
            "source_lineage": "same-owner",
            "source_digests": [{"evidence_hash": f"digest-{index}", "confidence": 0.9}],
        }
        source.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
        sources.append(source)

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=sources)
    provisional = report["unknown_project_lifecycle"]["provisional_candidates"][0]

    assert provisional["status"] == "collect_more_cases"
    assert provisional["independent_lineage_count"] == 1
    assert provisional["cluster_gaps"] == ["minimum_independent_lineages"]


def test_unknown_route_does_not_mutate_known_mature_baseline(tmp_path: Path) -> None:
    policy = load_role_project_type_policy()
    policy["evidence_thresholds"] = {
        "minimum_cases": 1,
        "minimum_blind_cases": 1,
        "minimum_independent_reports": 1,
    }
    known = tmp_path / "known.json"
    unknown = tmp_path / "unknown.json"
    known.write_text(json.dumps({"cases": [_case("known-cli", 10.0, 10.0)]}), encoding="utf-8")
    unknown.write_text(json.dumps({"cases": [_unknown_case("novel")]}), encoding="utf-8")

    report = build_role_project_type_evaluation(
        root=tmp_path,
        report_paths=[known, unknown],
        blind_report_paths=[known],
        policy=policy,
    )

    baseline = report["known_strata_regression_baseline"]
    assert baseline["status"] == "active"
    assert any(
        row["role_id"] == "project_analyzer" and row["project_stratum"] == "cli_local_tool"
        for row in baseline["protected_cells"]
    )
    assert _cell(report, "project_analyzer", "cli_local_tool")["maturity"] == "mature"
    assert report["maturity_status"] == "needs_work"


def test_workspace_roles_outside_scope_selection_are_not_applicable(tmp_path: Path) -> None:
    source = tmp_path / "workspace.json"
    source.write_text(json.dumps({"cases": [{
        "project": "dirty-workspace",
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "project_stratum": "workspace_portfolio",
        },
        "role_scores": {"project_analyzer": 9.7},
    }]}), encoding="utf-8")

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[source])

    implementer = _cell(report, "implementer", "workspace_portfolio")
    assert implementer["maturity"] == "not_applicable"
    assert implementer["applicable"] is False
    assert not any(
        row["role_id"] == "implementer" and row["project_stratum"] == "workspace_portfolio"
        for row in report["priority_queue"]
    )
    assert report["summary"]["not_applicable_cell_count"] == 24
    downstream = [
        cell for cell in report["cells"]
        if cell["project_stratum"] == "workspace_portfolio" and not cell["applicable"]
    ]
    assert all(cell["score"] is None for cell in downstream)
    assert all(cell["observation_count"] == 0 for cell in downstream)


def test_cli_entrypoint_identity_wins_over_internal_parser_archetype() -> None:
    classification = classify_project_case({
        "project": "dbcli__mycli",
        "artifacts": {
            "project_map_report": {
                "content": {
                    "source_health": {"entrypoint_count": 2, "project_shape": "single_project"},
                    "answers": {
                        "1_scope": {"domain_profile": {"kind": "configuration_file_parser_library"}}
                    },
                },
            }
        },
    })

    assert classification["project_stratum"] == "cli_local_tool"
    assert classification["classification_source"] == "entrypoint_identity_precedence"
    assert classification["effective_project_identity"] == "cli_local_tool"
    assert classification["project_archetype_scope"] == "internal_capability"


def test_cli_entrypoint_identity_wins_over_internal_database_archetype() -> None:
    classification = classify_project_case({
        "project": "dbcli__pgcli",
        "artifacts": {
            "project_map_report": {
                "content": {
                    "source_health": {"entrypoint_count": 1},
                    "answers": {
                        "1_scope": {"domain_profile": {"kind": "embedded_document_database_library"}}
                    },
                },
            }
        },
    })

    assert classification["project_stratum"] == "cli_local_tool"


def test_declared_distribution_script_does_not_require_cli_in_project_name() -> None:
    classification = classify_project_case({
        "project": "ott2__isabelle-layout",
        "artifacts": {
            "project_map_report": {
                "content": {
                    "source_health": {
                        "entrypoint_count": 1,
                        "declared_script_entrypoint_count": 1,
                    },
                    "answers": {
                        "1_scope": {"domain_profile": {"kind": "configuration_file_parser_library"}}
                    },
                },
            }
        },
    })

    assert classification["project_stratum"] == "cli_local_tool"
    assert classification["classification_source"] == "entrypoint_identity_precedence"
    assert classification["matched_markers"] == [
        "declared_script_entrypoint",
        "project_map_entrypoint",
    ]


def test_declared_script_overrides_low_confidence_packaging_text_profile() -> None:
    classification = classify_project_case({
        "project": "pypa__sampleproject",
        "artifacts": {"project_map_report": {"content": {
            "source_health": {"entrypoint_count": 1, "declared_script_entrypoint_count": 1},
            "answers": {"1_scope": {"domain_profile": {
                "kind": "packaging_build_backend", "confidence": 0.63,
            }}},
        }}},
    })

    assert classification["project_stratum"] == "cli_local_tool"
    assert classification["project_archetype_scope"] == "internal_capability"


def test_declared_plugin_identity_wins_over_script_entrypoint() -> None:
    classification = classify_project_case({
        "project": "sample__tool",
        "artifacts": {"project_map_report": {"content": {
            "source_health": {
                "entrypoint_count": 2,
                "declared_script_entrypoint_count": 1,
                "declared_plugin_entrypoint_count": 1,
            },
            "answers": {"1_scope": {"domain_profile": {
                "kind": "configuration_file_parser_library", "confidence": 0.63,
            }}},
        }}},
    })

    assert classification["project_stratum"] == "framework_plugin_build"
    assert classification["matched_markers"][0] == "declared_plugin_entrypoint"


def test_declared_script_does_not_override_source_backed_packaging_backend() -> None:
    classification = classify_project_case({
        "project": "pypa__build",
        "artifacts": {"project_map_report": {"content": {
            "source_health": {"entrypoint_count": 1, "declared_script_entrypoint_count": 1},
            "answers": {"1_scope": {"domain_profile": {
                "kind": "packaging_build_backend", "confidence": 0.79,
            }}},
        }}},
    })

    assert classification["project_stratum"] == "framework_plugin_build"


def test_researcher_is_conditional_for_known_project_strata(tmp_path: Path) -> None:
    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[])

    researcher = _cell(report, "researcher", "scientific_compute")
    assert researcher["applicable"] is False
    assert researcher["maturity"] == "not_applicable"


def test_downstream_case_inherits_known_foundation_project_classification(tmp_path: Path) -> None:
    foundation = tmp_path / "foundation.json"
    downstream = tmp_path / "downstream.json"
    foundation.write_text(json.dumps({"cases": [{
        "project": "cachelib",
        "artifacts": {"project_map_report": {"domain_profile": {"kind": "cache_backend_library"}}},
        "role_scores": {"project_analyzer": 9.7},
    }]}), encoding="utf-8")
    downstream.write_text(json.dumps({"cases": [{
        "project": "cachelib",
        "role_scores": {"implementer": 10.0},
    }]}), encoding="utf-8")

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[foundation, downstream])

    assert _cell(report, "implementer", "stateful_service_database")["score"] == 10.0


def test_newer_foundation_report_supersedes_same_project_snapshot(tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(json.dumps({
        "artifact_type": "RoleFoundationFieldTrialReport",
        "generated_at": "2026-08-25T00:00:00+00:00",
        "cases": [_case("cli-project", 6.0, 6.0)],
    }), encoding="utf-8")
    new.write_text(json.dumps({
        "artifact_type": "RoleFoundationFieldTrialReport",
        "generated_at": "2026-08-26T00:00:00+00:00",
        "cases": [_case("cli-project", 9.7, 9.7)],
    }), encoding="utf-8")

    report = build_role_project_type_evaluation(
        root=tmp_path, report_paths=[old, new], blind_report_paths=[old, new]
    )

    analyzer = _cell(report, "project_analyzer", "cli_local_tool")
    assert analyzer["score"] == 9.7
    assert analyzer["observation_count"] == 1
    assert [row["effective_case_count"] for row in report["sources"]] == [0, 1]


def test_project_identity_override_repairs_stale_explicit_classification() -> None:
    classified = classify_project_case({
        "project": "GoogleCloudPlatform__automlops",
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": "role_project_classification.2026-08-26.7",
            "project_stratum": "data_tabular_pipeline",
            "project_archetype": "derived_tabular_transform_benchmark",
        },
    })

    assert classified["project_stratum"] == "framework_plugin_build"
    assert classified["classification_source"] == "identity_override"

