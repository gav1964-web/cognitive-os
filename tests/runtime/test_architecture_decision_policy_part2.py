from __future__ import annotations

from tests.runtime.architecture_decision_policy_helpers import *

def test_architecture_decision_excludes_root_docs_src_tutorials(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adr = build_architecture_decision(
        goal="Extract model contract",
        project_report={
            "summary": {"root": project.as_posix(), "file_count": 2, "entrypoints": [], "languages": ["Python"]},
            "answers": {
                "1_scope": {"domain_profile": {"kind": "generic"}},
                "6_runtime_extraction_readiness": {"minimal_extraction_plan": {"capabilities_to_extract": [
                    {"capability": "docs_src/tutorial.py:create_db"},
                    {"capability": "sqlmodel/main.py:get_sqlalchemy_type"},
                ]}},
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["sqlmodel/main.py:get_sqlalchemy_type"]


def test_architecture_fallback_uses_plan_after_context_only_callable_is_rejected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    adr = build_architecture_decision(
        goal="Extract client contract",
        project_report={
            "summary": {"root": project.as_posix(), "file_count": 2, "entrypoints": [], "languages": ["Python"]},
            "answers": {
                "1_scope": {"domain_profile": {"kind": "protocol_api_client"}},
                "3_capabilities": {
                    "pure_transforms": [
                        {"path": "profiling/pyspy.py", "name": "vector_search", "args": []},
                    ],
                },
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "capabilities_to_extract": [
                            {"capability": "pkg/client.py:build_query"},
                        ],
                    },
                },
            },
        },
    )

    assert adr["first_slice_contract"]["targets"] == ["pkg/client.py:build_query"]


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
