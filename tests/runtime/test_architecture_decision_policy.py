from __future__ import annotations

from runtime.architecture_decision_builder import build_architecture_decision
from runtime.architecture_decision_policy import load_architecture_decision_policy


def test_architecture_decision_policy_loads_required_sections():
    policy = load_architecture_decision_policy()

    assert policy["schema_version"] == "architecture_decision_policy.v1"
    assert policy["fallback_archetype"]["service_frameworks"]
    assert policy["fallback_slice"]["steps"]
    assert policy["source_selection"]["context_only_path_tokens"]
    assert policy["source_selection"]["brief_sort_rules"]


def test_architecture_decision_policy_drives_fallback_and_source_selection(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "parser.py").write_text("def parse_payload(payload):\n    return {'ok': True}\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "example.py").write_text("def parse_payload(payload):\n    return {'doc': True}\n", encoding="utf-8")

    adr = build_architecture_decision(
        goal="Extract parser",
        project_report={
            "summary": {
                "root": project.as_posix(),
                "file_count": 2,
                "entrypoints": ["main.py"],
                "languages": ["Python"],
            },
            "answers": {
                "1_scope": {"domain_profile": {"kind": "generic"}},
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "goal": "Extract parser capability.",
                        "capabilities_to_extract": [
                            {"capability": "src/parser.py:parse_payload", "why": "source-backed parser"},
                            {"capability": "docs/example.py:parse_payload", "why": "context-only example"},
                        ],
                    },
                    "dataflows": [{"entrypoint": "main.py"}],
                },
            },
        },
    )

    assert adr["architecture_synthesis"]["project_profile"]["archetype"] == "python_cli_or_file_pipeline"
    assert adr["first_slice_contract"]["knowledge_rule"] == "project_map_report_minimal_extraction_plan"
    assert "src/parser.py:parse_payload" in adr["spec_writer_brief"]["files_or_symbols"]
    assert "docs/example.py:parse_payload" not in adr["spec_writer_brief"]["files_or_symbols"]


def test_architecture_decision_policy_allows_sphinx_conf_fallback_read_file(tmp_path):
    project = tmp_path / "docs_project"
    project.mkdir()
    (project / "source").mkdir()
    (project / "source" / "conf.py").write_text("extensions = ['sphinx.ext.autodoc']\n", encoding="utf-8")

    adr = build_architecture_decision(
        goal="Analyze docs project",
        project_report={
            "summary": {
                "root": project.as_posix(),
                "file_count": 1,
                "entrypoints": [],
                "languages": ["Python"],
                "read_files": ["source/conf.py"],
            },
            "answers": {
                "1_scope": {"domain_profile": {"kind": "documentation_project"}},
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {},
                    "dataflows": [],
                },
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["source/conf.py"]
    assert adr["spec_writer_brief"]["files_or_symbols"] == ["source/conf.py"]


def test_architecture_decision_policy_promotes_callable_transform_fallback(tmp_path):
    project = tmp_path / "runtime_project"
    project.mkdir()
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text(
        "def maybe_patch_concurrency(argv=None):\n    return argv or []\n",
        encoding="utf-8",
    )
    (project / "pkg" / "runtime.py").write_text(
        "def execute_runtime(app):\n    return app.run()\n",
        encoding="utf-8",
    )

    adr = build_architecture_decision(
        goal="Extract runtime option boundary",
        project_report={
            "summary": {
                "root": project.as_posix(),
                "file_count": 2,
                "entrypoints": ["pkg/runtime.py"],
                "languages": ["Python"],
            },
            "answers": {
                "1_scope": {"domain_profile": {"kind": "generic"}},
                "3_capabilities": {
                    "pure_transforms": [
                        {"path": "pkg/__init__.py", "name": "maybe_patch_concurrency"},
                    ],
                },
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "goal": "Extract runtime flow.",
                        "capabilities_to_extract": [
                            {"capability": "pkg/runtime.py:execute_runtime", "why": "central flow"},
                        ],
                    },
                    "dataflows": [{"entrypoint": "pkg/runtime.py"}],
                },
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["pkg/__init__.py:maybe_patch_concurrency"]
    assert "pkg/runtime.py:execute_runtime" in [
        row["source"] for row in adr["capability_model"] if row.get("source")
    ]


def test_architecture_decision_policy_promotes_profiled_transform_without_path_match(tmp_path):
    project = tmp_path / "profiled_project"
    project.mkdir()
    (project / "pkg").mkdir()
    (project / "pkg" / "helpers.py").write_text(
        "def normalize_name(name: str) -> str:\n    return name.strip().lower()\n",
        encoding="utf-8",
    )
    (project / "pkg" / "runtime.py").write_text("def execute_runtime(app):\n    return app.run()\n", encoding="utf-8")

    adr = build_architecture_decision(
        goal="Extract safe transform",
        project_report={
            "summary": {
                "root": project.as_posix(),
                "file_count": 2,
                "entrypoints": ["pkg/runtime.py"],
                "languages": ["Python"],
            },
            "answers": {
                "1_scope": {"domain_profile": {"kind": "generic"}},
                "3_capabilities": {
                    "pure_transforms": [
                        {
                            "path": "pkg/helpers.py",
                            "name": "normalize_name",
                            "args": [{"name": "name", "annotation": "str"}],
                            "returns": "str",
                        },
                    ],
                },
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "goal": "Extract runtime flow.",
                        "capabilities_to_extract": [
                            {"capability": "pkg/runtime.py:execute_runtime", "why": "central flow"},
                        ],
                    },
                    "dataflows": [{"entrypoint": "pkg/runtime.py"}],
                },
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["pkg/helpers.py:normalize_name"]


def test_architecture_decision_backfills_empty_first_slice_from_source_tasks(tmp_path):
    project = tmp_path / "zope.testing"
    project.mkdir()

    adr = build_architecture_decision(
        goal="Extract doctest execution",
        project_report={
            "summary": {"root": project.as_posix(), "file_count": 1, "entrypoints": [], "languages": ["Python"]},
            "architecture_synthesis": {
                "artifact_type": "ProjectArchitectureSynthesis",
                "recommended_first_slice": {
                    "name": "configuration_parse_lookup_slice",
                    "goal": "Prepare a bounded target.",
                    "targets": [],
                    "steps": ["Define the selected source contract."],
                },
            },
            "analysis_tasks": {
                "tasks": [
                    {
                        "type": "HARDEN_CONTRACT",
                        "target": "src/zope/testing/doctestcase.py:_run_test",
                        "title": "Harden doctest run contract",
                    }
                ]
            },
            "answers": {"1_scope": {"domain_profile": {"kind": "generic"}}},
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["src/zope/testing/doctestcase.py:_run_test"]
    assert adr["capability_model"][0]["source"] == "src/zope/testing/doctestcase.py:_run_test"


def test_architecture_decision_policy_keeps_pathless_sort_profile_out_of_fallback(tmp_path):
    project = tmp_path / "profiled_project"
    project.mkdir()
    (project / "pkg").mkdir()
    (project / "pkg" / "helpers.py").write_text(
        "def sort_emails_by_timestamp(emails: list) -> list:\n    return sorted(emails)\n",
        encoding="utf-8",
    )
    (project / "pkg" / "runtime.py").write_text("def execute_runtime(app):\n    return app.run()\n", encoding="utf-8")

    adr = build_architecture_decision(
        goal="Extract safe transform",
        project_report={
            "summary": {
                "root": project.as_posix(),
                "file_count": 2,
                "entrypoints": ["pkg/runtime.py"],
                "languages": ["Python"],
            },
            "answers": {
                "1_scope": {"domain_profile": {"kind": "generic"}},
                "3_capabilities": {
                    "pure_transforms": [
                        {
                            "path": "pkg/helpers.py",
                            "name": "sort_emails_by_timestamp",
                            "args": [{"name": "emails", "annotation": "list"}],
                            "returns": "list",
                        },
                    ],
                },
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "goal": "Extract runtime flow.",
                        "capabilities_to_extract": [
                            {"capability": "pkg/runtime.py:execute_runtime", "why": "central flow"},
                        ],
                    },
                    "dataflows": [{"entrypoint": "pkg/runtime.py"}],
                },
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["pkg/runtime.py:execute_runtime"]


def test_architecture_decision_excludes_context_only_first_slice_targets(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    adr = build_architecture_decision(
        goal="Extract runtime flow",
        project_report={
            "summary": {"root": project.as_posix(), "file_count": 2, "entrypoints": [], "languages": ["Python"]},
            "architecture_synthesis": {
                "artifact_type": "ProjectArchitectureSynthesis",
                "recommended_first_slice": {
                    "name": "runtime_slice",
                    "targets": ["pkg/runtime.py:run", "integration/test_runtime.py:run_case"],
                    "steps": ["Define the runtime contract."],
                },
            },
            "answers": {"1_scope": {"domain_profile": {"kind": "generic"}}},
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["pkg/runtime.py:run"]


def test_architecture_decision_promotes_pure_ast_parser_over_runtime_plan(tmp_path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "ast.py").write_text("def parse(source: str):\n    return source\n", encoding="utf-8")

    adr = build_architecture_decision(
        goal="Extract parser",
        project_report={
            "summary": {"root": project.as_posix(), "file_count": 1, "entrypoints": [], "languages": ["Python"]},
            "answers": {
                "1_scope": {"domain_profile": {"kind": "generic"}},
                "3_capabilities": {"pure_transforms": [{"path": "pkg/ast.py", "name": "parse", "args": [{"name": "source", "annotation": "str"}]}]},
                "6_runtime_extraction_readiness": {"minimal_extraction_plan": {"capabilities_to_extract": [{"capability": "pkg/cache.py:refresh"}]}},
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["pkg/ast.py:parse"]
