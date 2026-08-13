from plugins.project_map_report.src.main import run


def test_project_map_report_treats_newer_python_syntax_as_parser_limit():
    result = run(
        {
            "tree": {"root": "modern", "counts": {"files": 2, "directories": 1}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": [], "dependency_files": []},
            "files": {"files": [], "skipped": []},
            "python_structure": {
                "files": [{"path": "app.py", "functions": []}],
                "skipped": [{"path": "cache.py", "reason": "ParserVersionIncompatible", "line": 1}],
            },
            "runtime_commands": {"commands": [], "skipped": []},
        }
    )

    health = result["source_health"]
    assert health["status"] == "noisy"
    assert health["syntax_error_count"] == 0
    assert health["parser_incompatibility_count"] == 1
    assert health["inaccessible_count"] == 0


def test_project_map_report_uses_domain_flow_anchor_for_first_slice():
    result = run(
        {
            "tree": {"root": "prefect", "counts": {"files": 3, "directories": 2, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": [], "large_artifacts": [], "dependency_files": []},
            "files": {"files": []},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [
                    {"path": "prefect/task_engine/runtime.py", "functions": []},
                    {"path": "prefect/utils/helpers.py", "functions": []},
                ],
                "domain_flow_anchors": [
                    {
                        "path": "prefect/task_engine/runtime.py",
                        "name": "run_task_engine",
                        "line": 1,
                        "loc": 40,
                        "call_count": 8,
                        "side_effects": [],
                    }
                ],
                "central_nodes": [
                    {
                        "path": "prefect/utils/helpers.py",
                        "name": "validate_key",
                        "line": 1,
                        "loc": 90,
                        "call_count": 12,
                        "side_effects": [],
                    }
                ],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
            },
            "runtime_commands": {"commands": []},
        }
    )

    capabilities = result["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"]["capabilities_to_extract"]
    assert capabilities[0]["capability"] == "prefect/task_engine/runtime.py:run_task_engine"
    assert capabilities[0]["candidate_level"] == "core_flow"


def test_project_map_report_skips_non_purpose_doc_headings_for_main_task():
    result = run(
        {
            "tree": {"root": "project", "counts": {"files": 2, "directories": 1, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": [], "large_artifacts": [], "dependency_files": []},
            "files": {
                "files": [
                    {"path": "AGENTS.md", "text": "# AGENTS.md\n"},
                    {"path": "CLAUDE.md", "text": "# CLAUDE.md\n"},
                    {"path": "CHANGES/README.rst", "text": "Change notes\n============\n"},
                    {"path": "examples/README.rst", "text": "Example Project\n===============\n"},
                    {"path": "packaging/pep517_backend/README.md", "text": "# `pep517_backend` in-tree build backend\n"},
                    {"path": "README.rst", "text": "# <div align=\"center\">logo</div>\nReal Package\n============\n"},
                    {"path": "CONTRIBUTORS.txt", "text": "# Contributors (alphabetical order)\n"},
                ]
            },
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "src/pkg/__init__.py", "functions": []}],
                "central_nodes": [],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
            },
            "runtime_commands": {"commands": []},
        }
    )

    assert result["answers"]["1_scope"]["main_task"].startswith("Inferred from docs: Real Package")


def test_project_map_report_prefers_descriptive_heading_over_warning_paragraph():
    from plugins.project_map_report.src.doc_purpose import descriptive_purpose_heading

    docs = "# Tool is a self-hosted app for automating Docker container updates\n\nPlease do not use it in production.\n"

    assert descriptive_purpose_heading(docs).startswith("Tool is a self-hosted app")


def test_package_init_entrypoint_still_counts_as_library_surface():
    result = run(
        {
            "tree": {
                "root": "project",
                "counts": {"files": 2, "directories": 2, "truncated": False},
                "files": [{"path": "pyproject.toml"}, {"path": "src/demo/__init__.py"}],
            },
            "stack": {
                "languages": [{"language": "Python"}, {"language": ".toml"}],
                "frameworks": [],
                "entrypoints": ["src/demo/__init__.py"],
            },
            "files": {"files": [{"path": "pyproject.toml", "text": "[project]\nname='demo'\n"}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "src/demo/__init__.py", "functions": [{"path": "src/demo/__init__.py", "name": "parse"}]}],
                "project_insights": {},
            },
            "runtime_commands": {"commands": []},
        }
    )
    scope = result["answers"]["1_scope"]

    assert len(scope["supported_scenarios"]) >= 3
    assert "Import package modules" in scope["supported_scenarios"][0]


def test_package_internal_main_module_still_counts_as_library_surface():
    result = run(
        {
            "tree": {
                "root": "project",
                "counts": {"files": 2, "directories": 1, "truncated": False},
                "files": [{"path": "pyproject.toml"}, {"path": "demo/main.py"}],
            },
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": ["demo/main.py"],
            },
            "files": {"files": [{"path": "pyproject.toml", "text": "[project]\nname='demo'\n"}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "demo/main.py", "functions": [{"path": "demo/main.py", "name": "build_values"}]}],
                "project_insights": {},
            },
            "runtime_commands": {"commands": []},
        }
    )
    scope = result["answers"]["1_scope"]

    assert "Import package modules" in scope["supported_scenarios"][0]


def test_project_map_report_synthesizes_llm_gateway_purpose_above_fastapi_transport():
    result = run(
        {
            "tree": {"root": "llm_gateway", "counts": {"files": 5, "directories": 3, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": ["FastAPI"], "entrypoints": ["app/api/server.py"], "large_artifacts": [], "dependency_files": []},
            "files": {
                "files": [
                    {"path": "config/providers.yaml", "text": "providers:\n  openai: {}\n  deepseek: {}\nrouting_profiles:\n  default_chat: []\n"},
                    {"path": "docs/USAGE.md", "text": "Gateway examples for /v1/chat/completions and provider routing.\n"},
                ]
            },
            "python_structure": {
                "imports": ["fastapi", "httpx", "openai"],
                "routes": [{"route": "/v1/chat/completions", "path": "app/api/handlers_openai.py", "function": "handle_chat_completions"}],
                "files": [
                    {"path": "app/api/server.py", "functions": []},
                    {"path": "app/api/routing.py", "functions": []},
                    {"path": "app/providers/factory.py", "functions": []},
                ],
                "central_nodes": [],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {"llm": ["openai"], "network": ["httpx", "openai"]},
            },
            "runtime_commands": {"commands": []},
        }
    )

    scope = result["answers"]["1_scope"]
    execution = result["answers"]["2_execution"]

    assert scope["domain_profile"]["kind"] == "llm_provider_gateway"
    assert scope["main_task"].startswith("Provide a unified OpenAI-compatible gateway")
    assert "Expose an HTTP API service" not in scope["main_task"]
    assert any("LLM provider" in scenario for scenario in scope["supported_scenarios"])
    assert execution["primary_execution_path"][0] == "OpenAI-compatible HTTP request"


def test_project_map_report_uses_kb_profile_for_prompt_lab_scope():
    result = run(
        {
            "tree": {"root": "prompt_lab", "counts": {"files": 5, "directories": 2, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": ["FastAPI"], "entrypoints": ["prompt_lab.py", "prompt_lab_api.py"], "large_artifacts": [], "dependency_files": []},
            "files": {
                "files": [
                    {"path": "README.md", "text": "Gateway-ish examples may mention /v1/chat/completions, but this is a prompt-lab workspace."},
                    {"path": "prompt_lab.py", "text": "def render_validation_prompt(): pass\ndef run_auto_loop_once(): pass\n"},
                ]
            },
            "python_structure": {
                "imports": ["fastapi", "httpx"],
                "routes": [{"route": "/jobs", "path": "prompt_lab_api.py", "function": "submit_job"}],
                "files": [
                    {
                        "path": "prompt_lab.py",
                        "functions": [
                            {"path": "prompt_lab.py", "name": "render_validation_prompt", "calls": []},
                            {"path": "prompt_lab.py", "name": "run_auto_loop_once", "calls": ["render_validation_prompt"]},
                            {"path": "prompt_lab.py", "name": "analyze_validation_results", "calls": []},
                        ],
                    },
                    {"path": "prompt_lab_api.py", "functions": [{"path": "prompt_lab_api.py", "name": "create_app", "calls": []}]},
                ],
                "central_nodes": [{"path": "prompt_lab.py", "name": "run_auto_loop_once", "loc": 90, "call_count": 5}],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {"network": ["httpx"]},
            },
            "runtime_commands": {"commands": []},
        }
    )

    scope = result["answers"]["1_scope"]

    assert scope["domain_profile"]["kind"] == "prompt_lab_evaluation_runtime"
    assert scope["domain_profile"]["knowledge_rule"] == "prompt_lab_evaluation_runtime"
    assert scope["main_task"].startswith("Run a prompt laboratory")
    assert any("prompt-lab workspace" in scenario for scenario in scope["supported_scenarios"])
    assert "OpenAI-compatible gateway" not in scope["main_task"]


def test_project_map_report_exposes_dirty_portfolio_source_health():
    entrypoints = [f"run_{index}/api_server.py" for index in range(25)]
    result = run(
        {
            "tree": {
                "root": "workspace",
                "counts": {"files": 2000, "directories": 800, "truncated": True},
                "files": [{"path": "run_1/generated/app.py"}, {"path": "run_2/scratch/report.md"}],
                "skipped": {
                    "files": 2,
                    "directories": 1,
                    "too_deep": 4,
                    "truncated_files": 10,
                    "inaccessible_files": 2,
                    "inaccessible_directories": 1,
                },
            },
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": ["FastAPI"],
                "entrypoints": entrypoints,
                "large_artifacts": [],
                "dependency_files": [{"path": f"run_{index}/requirements.txt", "dependencies": ["fastapi"]} for index in range(25)],
            },
            "files": {"files": [], "skipped": []},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "run_1/generated/app.py", "functions": []}],
                "central_nodes": [],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
                "skipped": [{"path": "broken.py", "reason": "SyntaxError", "line": 1}],
            },
            "runtime_commands": {"commands": [], "skipped": [{"path": "bad/run.bat", "reason": "OSError"}]},
        }
    )

    health = result["source_health"]
    assert health["status"] == "damaged"
    assert health["project_shape"] == "dirty_portfolio"
    assert health["syntax_error_count"] == 1
    assert health["inaccessible_count"] >= 4
    assert result["summary"]["project_shape"] == "dirty_portfolio"
    assert result["answers"]["0_source_health"] == health
    assert {risk["code"] for risk in result["risks"]} >= {
        "dirty_portfolio_detected",
        "inaccessible_paths",
        "python_syntax_errors",
        "source_health_not_clean",
        "tree_scan_truncated",
    }
    assert "choose a concrete project root" in health["recommendation"]
    assert "## Source Health" in result["markdown"]


def test_project_map_report_does_not_treat_src_build_package_as_generated_noise():
    result = run(
        {
            "tree": {
                "root": "build",
                "counts": {"files": 3, "directories": 2, "truncated": False},
                "files": [
                    {"path": "pyproject.toml"},
                    {"path": "src/build/__main__.py"},
                    {"path": "src/build/_builder.py"},
                ],
            },
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": [],
                "dependency_files": [{"path": "pyproject.toml", "dependencies": []}],
            },
            "files": {"files": []},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [
                    {
                        "path": "src/build/__main__.py",
                        "functions": [{"path": "src/build/__main__.py", "name": "_validate_sdist_archive", "loc": 30}],
                    },
                    {"path": "src/build/_builder.py", "functions": []},
                ],
                "central_nodes": [],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
                "skipped": [],
            },
            "runtime_commands": {"commands": [], "skipped": []},
        }
    )

    health = result["source_health"]
    assert health["generated_run_signal_count"] == 0
    assert health["status"] == "clean"
