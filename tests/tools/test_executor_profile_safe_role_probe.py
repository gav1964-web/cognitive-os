from __future__ import annotations

from pathlib import Path

from tools.executor_profile_safe_role_probe import (
    _discover_domain_lineage_rows,
    _discover_rows,
    _domain_benchmark_rows,
    run_profile_safe_role_probe,
)

EXPECTED_ROLE_SCORES = {
    "project_analyzer": 10.0,
    "architect": 10.0,
    "spec_writer": 10.0,
    "implementer": 10.0,
    "tester": 10.0,
    "reviewer": 10.0,
}


def test_executor_profile_safe_role_probe_runs_role_chain(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "helpers.py").write_text(
        "def normalize_name(name: str) -> str:\n"
        "    return name\n\n"
        "def sort_items(items: list) -> list:\n"
        "    return items\n",
        encoding="utf-8",
    )

    report = run_profile_safe_role_probe(root=tmp_path, projects_dir=projects, label="test", limit=5)

    assert report["status"] == "ok"
    assert report["summary"]["accepted"] == 1
    assert report["summary"]["profiles"] == {"normalize_string": 1}
    assert report["summary"]["patch_transforms"] == {"strip_lower": 1}
    assert report["source_lineage"] == projects.resolve().as_posix()
    case = report["cases"][0]
    assert case["role_scores"] == EXPECTED_ROLE_SCORES
    assert case["generated_function_stub_admission"]["status"] == "passed"
    assert report["summary"]["generated_stub_count"] == 0
    assert case["control_test_result_status"] == "failed"
    assert case["control_acceptance_status"] == "passed"
    assert case["passing_review_recommendation"] in {"approve", "approve_with_risks"}
    assert case["failing_review_recommendation"] == "request_rework"
    assert case["programmer_evidence"]["transformation_evaluated"] is True


def test_discovery_finds_nested_registered_operator(tmp_path: Path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "helpers.py").write_text(
        "def outer():\n"
        "    def first_item(value):\n"
        "        return value[0]\n"
        "    return first_item\n",
        encoding="utf-8",
    )

    rows = _discover_rows(tmp_path, limit=5, max_per_project=5)

    assert [(row["source_target"], row["operator_id"]) for row in rows] == [
        ("helpers.py:first_item", "first_item")
    ]
    assert rows[0]["mutation_source"] == "real_operator_replaced_with_identity"


def test_discovery_allows_defaults_for_exact_registered_operator(tmp_path: Path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "helpers.py").write_text(
        "def is_console(value=str):\n"
        "    return value.startswith('CON.1')\n",
        encoding="utf-8",
    )

    rows = _discover_rows(tmp_path, limit=5, max_per_project=5)

    assert [(row["source_target"], row["operator_id"]) for row in rows] == [
        ("helpers.py:is_con1", "starts_with_con1")
    ]


def test_domain_benchmark_expands_each_project_to_three_distinct_training_contracts():
    rows = [
        {
            "project": "policy-lab",
            "source_target": "common/utils.py:discount_rewards",
            "symbol": "discount_rewards",
        }
    ]

    expanded = _domain_benchmark_rows(rows, "ml_training_checkpoint")

    assert {row["operator_id"] for row in expanded} == {
        "clip_signed_unit",
        "decay_rate",
        "discount_returns",
    }
    assert {row["source_target"] for row in expanded} == {"common/utils.py:discount_rewards"}
    assert all(row["mutation_source"] == "domain_contract_identity_benchmark" for row in expanded)


def test_domain_lineage_uses_ranked_extraction_target(tmp_path: Path, monkeypatch):
    from tools import executor_profile_safe_role_probe as probe

    project = tmp_path / "pytorch-ood"
    project.mkdir()
    monkeypatch.setattr(
        probe,
        "analyze_project",
        lambda _path: {
            "project_map_report": {
                "answers": {
                    "3_capabilities": {
                        "pure_transforms": [{"path": "api.py", "name": "fit"}],
                    },
                    "6_runtime_extraction_readiness": {
                        "minimal_extraction_plan": {
                            "capabilities_to_extract": [
                                {"capability": "api.py:predict_features"},
                            ],
                        },
                    },
                },
            },
        },
    )

    rows = _discover_domain_lineage_rows(tmp_path, {"pytorch-ood"})

    assert rows[0]["source_target"] == "api.py:predict_features"


def test_discovery_skips_python_path_that_disappears_during_scan(tmp_path: Path, monkeypatch):
    from tools import executor_profile_safe_role_probe as probe

    path = tmp_path / "vanished.py"
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: (_ for _ in ()).throw(FileNotFoundError(self)))

    assert probe._path_rows(tmp_path, path, {"normalize_string"}) == []


def test_named_project_discovery_does_not_scan_sibling_projects(tmp_path: Path, monkeypatch):
    from tools import executor_profile_safe_role_probe as probe

    selected = tmp_path / "selected"
    sibling = tmp_path / "broken-sibling"
    selected.mkdir()
    sibling.mkdir()
    (selected / "helpers.py").write_text("def first_item(value): return value[0]\n", encoding="utf-8")
    original = Path.rglob

    def guarded_rglob(self, pattern):
        if self == tmp_path:
            raise AssertionError("corpus root must not be scanned for an explicit project")
        return original(self, pattern)

    monkeypatch.setattr(Path, "rglob", guarded_rglob)

    rows = probe._discover_rows(
        tmp_path, limit=3, max_per_project=3, project_names={"selected"}
    )

    assert rows[0]["project"] == "selected"


def test_cli_stratum_requires_process_level_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-cli"
    project.mkdir(parents=True)
    (project / "command.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    for interface in ("argv_json", "stdin_json", "file_json"):
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"cli-test-{interface}",
            limit=3,
            project_stratum="cli_local_tool",
            cli_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert report["invariants"]["maturity_scope"] == "cli_local_tool"
        assert case["project_classification"]["project_stratum"] == "cli_local_tool"
        assert case["project_classification"]["project_subtype"] == f"{interface}_stdout_json"
        assert case["cli_evidence"]["patched"]["status"] == "passed"
        assert case["cli_evidence"]["patched"]["invalid_returncode"] == 2
        assert "Traceback" not in case["cli_evidence"]["patched"]["invalid_stderr_tail"]
        assert case["cli_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES


def test_web_stratum_requires_http_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-web"
    project.mkdir(parents=True)
    (project / "endpoint.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    for interface in ("post_json", "get_query", "header_json"):
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"web-test-{interface}",
            limit=3,
            project_stratum="web_api_middleware",
            web_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert case["project_classification"]["project_subtype"] == f"{interface}_http_json"
        assert case["web_evidence"]["patched"]["status"] == "passed"
        assert case["web_evidence"]["patched"]["invalid_status_code"] == 400
        assert case["web_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES


def test_provider_stratum_requires_fixture_transport_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-provider"
    project.mkdir(parents=True)
    (project / "adapter.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    for interface in ("data_envelope", "choices_envelope", "paged_envelope"):
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"provider-test-{interface}",
            limit=3,
            project_stratum="sdk_provider_integration",
            provider_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert case["project_classification"]["project_subtype"] == (
            f"{interface}_provider_response"
        )
        assert case["provider_evidence"]["patched"]["status"] == "passed"
        assert case["provider_evidence"]["patched"]["call_count"] == 1
        assert case["provider_evidence"]["patched"]["invalid_returncode"] == 2
        assert "Traceback" not in case["provider_evidence"]["patched"]["invalid_stderr_tail"]
        assert case["provider_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES


def test_stateful_stratum_requires_persisted_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-state"
    project.mkdir(parents=True)
    (project / "records.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    for interface in ("insert_read", "update_read", "transaction_read"):
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"state-test-{interface}",
            limit=3,
            project_stratum="stateful_service_database",
            stateful_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert case["project_classification"]["project_subtype"] == f"{interface}_sqlite"
        assert case["stateful_evidence"]["patched"]["status"] == "passed"
        assert case["stateful_evidence"]["patched"]["row_count"] == 1
        assert case["stateful_evidence"]["patched"]["invalid_row_count"] == 0
        assert case["stateful_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES


def test_async_stratum_requires_scheduled_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-async"
    project.mkdir(parents=True)
    (project / "worker.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    for interface in ("await_once", "gather_batch", "queue_worker"):
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"async-test-{interface}",
            limit=3,
            project_stratum="async_worker_scheduler",
            async_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert case["project_classification"]["project_subtype"] == f"{interface}_async"
        assert case["async_evidence"]["patched"]["status"] == "passed"
        assert case["async_evidence"]["patched"]["task_count"] == 1
        assert case["async_evidence"]["patched"]["timeout_returncode"] == 2
        assert case["async_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES


def test_external_io_stratum_requires_boundary_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-io"
    project.mkdir(parents=True)
    (project / "boundary.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    for interface in ("file_roundtrip", "subprocess_pipe", "zip_archive"):
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"io-test-{interface}",
            limit=3,
            project_stratum="external_process_io",
            io_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert case["project_classification"]["project_subtype"] == f"{interface}_boundary"
        assert case["io_evidence"]["patched"]["status"] == "passed"
        assert case["io_evidence"]["patched"]["operation_count"] == 1
        assert case["io_evidence"]["patched"]["invalid_returncode"] == 2
        assert case["io_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES


def test_framework_stratum_requires_extension_or_artifact_behavior_change(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo-framework"
    project.mkdir(parents=True)
    (project / "extension.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name\n",
        encoding="utf-8",
    )

    interfaces = ("plugin_hook", "package_build", "code_generation", "docs_render")
    for interface in interfaces:
        report = run_profile_safe_role_probe(
            root=tmp_path,
            projects_dir=projects,
            label=f"framework-test-{interface}",
            limit=3,
            project_stratum="framework_plugin_build",
            framework_interface=interface,
        )

        case = report["cases"][0]
        assert report["status"] == "ok"
        assert case["project_classification"]["project_subtype"] == (
            f"{interface}_framework"
        )
        assert case["framework_evidence"]["patched"]["status"] == "passed"
        assert case["framework_evidence"]["patched"]["effect_count"] == 1
        assert case["framework_evidence"]["patched"]["invalid_returncode"] == 2
        assert case["framework_evidence"]["identity_control"]["status"] == "failed"
        assert case["role_scores"] == EXPECTED_ROLE_SCORES
