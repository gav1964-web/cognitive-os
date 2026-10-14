from tools.github_rebuild_corpus import _behavior_depth, _corpus_verdict, _quality_scores, _run_one, _summary
from runtime.source_unavailable_reason import source_unavailable_reason


def test_corpus_quality_uses_weakest_layer_for_confidence():
    trial = {
        "spec": {
            "artifact_type": "ProjectRebuildSpec",
            "target_name": "sample",
            "main_task": "rebuild",
            "entrypoints": ["sample:main"],
            "supported_scenarios": ["cli"],
            "core_capabilities": ["run"],
            "quality_targets": ["contract tests"],
        }
    }
    comparison = {
        "checks": {
            "has_app_entrypoint": True,
            "has_readme": True,
            "has_contract_tests": True,
            "compiles": True,
            "contract_tests_pass": True,
        }
    }
    quality = _quality_scores(
        trial,
        comparison,
        {
            "http_probes": 0,
            "module_import_probes": 2,
            "manifest_probes": 0,
            "source_ok": 0,
            "source_unavailable": 2,
        },
    )

    assert quality["mean_score"] == 0.75
    assert quality["behavior_score"] == 0.0
    assert quality["conservative_score"] == 0.0
    assert quality["confidence"] == 0.0
    assert _corpus_verdict(quality) == "needs_review"


def test_corpus_quality_counts_failed_generated_behavior_probes():
    trial = {
        "spec": {
            "artifact_type": "ProjectRebuildSpec",
            "target_name": "sample",
            "main_task": "rebuild",
            "entrypoints": ["sample:main"],
            "supported_scenarios": ["cli"],
            "core_capabilities": ["run"],
            "quality_targets": ["contract tests"],
        }
    }
    comparison = {
        "checks": {
            "has_app_entrypoint": True,
            "has_readme": True,
            "has_contract_tests": True,
            "compiles": True,
            "contract_tests_pass": True,
        },
        "behavior": {"summary": {"total": 2, "passed": 1, "failed": 1}},
    }
    quality = _quality_scores(
        trial,
        comparison,
        {
            "http_probes": 0,
            "module_import_probes": 2,
            "manifest_probes": 0,
            "source_ok": 2,
            "source_unavailable": 0,
        },
    )

    assert quality["behavior_score"] == 0.5
    assert quality["conservative_score"] == 0.5
    assert _corpus_verdict(quality) == "needs_review"


def test_corpus_quality_counts_stubbed_source_as_partial_evidence():
    trial = {
        "spec": {
            "artifact_type": "ProjectRebuildSpec",
            "target_name": "sample",
            "main_task": "rebuild",
            "entrypoints": ["sample:main"],
            "supported_scenarios": ["cli"],
            "core_capabilities": ["run"],
            "quality_targets": ["contract tests"],
        }
    }
    comparison = {
        "checks": {
            "has_app_entrypoint": True,
            "has_readme": True,
            "has_contract_tests": True,
            "compiles": True,
            "contract_tests_pass": True,
        },
        "behavior": {"summary": {"total": 1, "passed": 1, "failed": 0}},
    }
    quality = _quality_scores(
        trial,
        comparison,
        {
            "http_probes": 0,
            "module_import_probes": 1,
            "manifest_probes": 0,
            "source_ok": 1,
            "source_stubbed": 1,
            "source_unavailable": 0,
        },
    )

    assert quality["behavior_score"] == 0.65
    assert quality["conservative_score"] == 0.65
    assert _corpus_verdict(quality) == "needs_review"


def test_corpus_summary_reports_conservative_average_and_legacy_average():
    rows = [
        {
            "status": "ok",
            "score": 1.0,
            "quality": {"conservative_score": 1.0, "behavior_score": 1.0},
            "corpus_verdict": "behavior_checked",
            "behavior_depth": {"source_dependency_stubs": {"sqlalchemy": 1}},
        },
        {
            "status": "ok",
            "score": 1.0,
            "quality": {"conservative_score": 0.0, "behavior_score": 0.0},
            "corpus_verdict": "needs_review",
            "behavior_depth": {"source_dependency_stubs": {"sqlalchemy": 2, "rich": 1}},
        },
    ]

    summary = _summary(rows)

    assert summary["average_score"] == 0.5
    assert summary["legacy_average_score"] == 1.0
    assert summary["worst_score"] == 0.0
    assert summary["verdicts"] == {"behavior_checked": 1, "needs_review": 1}
    assert summary["source_dependency_stubs"] == {"rich": 1, "sqlalchemy": 3}


def test_corpus_summary_counts_any_prepared_probe_env_run():
    summary = _summary(
        [
            {
                "status": "ok",
                "quality": {"conservative_score": 0.65},
                "probe_env_prepare": {"status": "skipped"},
                "probe_env_prepare_runs": [{"status": "prepared"}, {"status": "skipped"}],
            }
        ]
    )

    assert summary["probe_env_prepared"] == 1


def test_corpus_row_score_is_conservative_score(tmp_path):
    source = tmp_path / "repos"
    rebuilt = tmp_path / "rebuilt"
    project = source / "owner_repo"
    project.mkdir(parents=True)
    rebuilt.mkdir()

    def runner(**_kwargs):
        return {
            "status": "ok",
            "spec": {
                "artifact_type": "ProjectRebuildSpec",
                "target_name": "sample",
                "main_task": "rebuild",
                "entrypoints": ["sample:main"],
                "supported_scenarios": ["cli"],
                "core_capabilities": ["run"],
                "quality_targets": ["contract tests"],
            },
            "comparison": {
                "score": 1.0,
                "checks": {
                    "has_app_entrypoint": True,
                    "has_readme": True,
                    "has_contract_tests": True,
                    "compiles": True,
                    "contract_tests_pass": True,
                },
                "behavior": {"summary": {"total": 1, "passed": 1, "failed": 0}},
                "probe_env": {},
            },
        }

    def env_preparer(**_kwargs):
        return {"status": "skipped"}

    row = _run_one(tmp_path, source, rebuilt, "owner/repo", False, False, runner, env_preparer)

    assert row["legacy_score"] == 1.0
    assert row["score"] == 0.0
    assert row["quality"]["conservative_score"] == 0.0


def test_source_unavailable_reasons_capture_current_corpus_gaps():
    assert source_unavailable_reason("no supported app adapter") == "unsupported_web_app_adapter"
    assert source_unavailable_reason("TypeError: 'ExtensionManager' object is not iterable") == "plugin_loader_side_effect"
    assert source_unavailable_reason("AssertionError: ") == "import_time_assertion"
    assert (
        source_unavailable_reason("TypeError: 'FunctionNamespace' object does not support item assignment")
        == "import_time_side_effect"
    )


def test_corpus_behavior_depth_counts_stubbed_http_source():
    depth = _behavior_depth(
        {
            "cases": [
                {
                    "probe": {"kind": "http"},
                    "source": {"status": "ok", "dependency_stubs": ["static_http_route_fallback"]},
                }
            ]
        }
    )

    assert depth["http_probes"] == 1
    assert depth["source_ok"] == 1
    assert depth["source_stubbed"] == 1
    assert depth["source_dependency_stubs"] == {"static_http_route_fallback": 1}
    assert depth["source_evidence_score"] == 0.7


def test_corpus_quality_uses_weighted_source_evidence_score():
    trial = {
        "spec": {
            "artifact_type": "ProjectRebuildSpec",
            "target_name": "sample",
            "main_task": "rebuild",
            "entrypoints": ["sample:main"],
            "supported_scenarios": ["http"],
            "routes": [{"route": "/"}],
            "quality_targets": ["contract tests"],
        }
    }
    comparison = {
        "checks": {
            "has_app_entrypoint": True,
            "has_readme": True,
            "has_contract_tests": True,
            "compiles": True,
            "contract_tests_pass": True,
        },
        "behavior": {"summary": {"total": 1, "passed": 1, "failed": 0}},
    }

    quality = _quality_scores(
        trial,
        comparison,
        {
            "http_probes": 1,
            "module_import_probes": 0,
            "manifest_probes": 0,
            "source_ok": 1,
            "source_stubbed": 1,
            "source_evidence_score": 0.7,
            "source_unavailable": 0,
        },
    )

    assert quality["behavior_score"] == 0.7
    assert quality["conservative_score"] == 0.7
