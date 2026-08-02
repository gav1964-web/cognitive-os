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
