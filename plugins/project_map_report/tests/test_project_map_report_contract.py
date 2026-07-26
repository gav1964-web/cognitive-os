from plugins.project_map_report.src.main import run


def test_python_library_without_cli_gets_library_usage_flow():
    result = run(
        {
            "tree": {
                "root": "project",
                "counts": {"files": 3, "directories": 2, "truncated": False},
                "files": [{"path": "pyproject.toml"}, {"path": "src/demo/__init__.py"}, {"path": "src/demo/core.py"}],
            },
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": []},
            "files": {
                "files": [
                    {"path": "pyproject.toml", "text": "[project]\nname = 'demo'\n"},
                    {"path": "README.md", "text": "# Demo\n\nDemo provides reusable Python data processing APIs."},
                ]
            },
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "src/demo/core.py", "functions": [{"path": "src/demo/core.py", "name": "process", "loc": 20}]}],
                "project_insights": {},
            },
            "runtime_commands": {"commands": []},
        }
    )

    scope = result["answers"]["1_scope"]
    execution = result["answers"]["2_execution"]
    assert "Import package modules" in scope["supported_scenarios"][0]
    assert execution["primary_execution_path"][0] == "user imports package/API"


def test_project_map_report_builds_markdown_and_risks():
    result = run(
        {
            "tree": {"root": "project", "counts": {"files": 2, "directories": 1, "truncated": False}},
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": ["Flask-like Python web app"],
                "entrypoints": ["app.py"],
                "large_artifacts": [{"path": "data.bin", "size_bytes": 100000000}],
                "dependency_files": [{"path": "requirements.txt", "dependencies": ["Flask"]}],
            },
            "files": {"files": [{"path": "README.md"}]},
            "python_structure": {
                "imports": ["subprocess"],
                "routes": [{"route": "/", "path": "app.py", "function": "index"}],
                "files": [
                    {
                        "path": "app.py",
                        "functions": [
                            {
                                "path": "app.py",
                                "name": "index",
                                "line": 10,
                                "loc": 90,
                                "calls": ["open", "json.dumps", "requests.get", "render_template", "helper"],
                                "side_effects": ["filesystem", "network"],
                                "error_profile": {"has_try": True, "raises": ["ValueError"], "handlers": ["Exception"]},
                            }
                        ],
                    },
                    {
                        "path": "tests/test_app.py",
                        "functions": [
                            {
                                "path": "tests/test_app.py",
                                "name": "test_normalize",
                                "line": 1,
                                "loc": 3,
                                "calls": [],
                                "side_effects": [],
                                "error_profile": {},
                            }
                        ],
                    },
                    {
                        "path": "tools/build_package.py",
                        "functions": [
                            {
                                "path": "tools/build_package.py",
                                "name": "copy_dist",
                                "line": 1,
                                "loc": 3,
                                "calls": [],
                                "side_effects": [],
                                "error_profile": {},
                            }
                        ],
                    },
                    {
                        "path": "_project_analyzer_extract.py",
                        "functions": [
                            {
                                "path": "_project_analyzer_extract.py",
                                "name": "check_python_syntax",
                                "line": 1,
                                "loc": 8,
                                "calls": ["Path.read_text"],
                                "side_effects": ["filesystem_read"],
                                "error_profile": {},
                            }
                        ],
                    },
                    {
                        "path": "map_install_package/app.py",
                        "functions": [
                            {
                                "path": "map_install_package/app.py",
                                "name": "index",
                                "line": 10,
                                "loc": 120,
                                "calls": ["open", "json.dumps", "render_template"],
                                "side_effects": ["filesystem"],
                                "error_profile": {},
                            }
                        ],
                    },
                ],
                "central_nodes": [
                    {"path": "map_install_package/app.py", "name": "index", "line": 10, "loc": 120, "call_count": 20, "side_effects": ["filesystem"]},
                    {"path": "app.py", "name": "index", "line": 10, "loc": 90, "call_count": 12, "side_effects": ["filesystem"]},
                ],
                "wide_functions": [
                    {"path": "map_install_package/app.py", "name": "index", "line": 10, "loc": 120, "call_count": 20, "side_effects": ["filesystem"]},
                    {"path": "app.py", "name": "index", "line": 10, "loc": 90, "call_count": 12, "side_effects": ["filesystem"]},
                ],
                "pure_transform_candidates": [
                    {"path": "tests/test_app.py", "name": "test_normalize", "line": 1, "loc": 3},
                    {"path": "tools/build_package.py", "name": "copy_dist", "line": 1, "loc": 3},
                    {"path": "app.py", "name": "normalize", "line": 2, "loc": 10},
                ],
                "project_insights": {
                    "test_surface": {"test_files": 1, "test_functions": 2},
                    "error_handling": {"raises": ["ValueError"], "handlers": ["Exception"], "functions_with_try": ["app.py:index"]},
                },
            },
            "runtime_commands": {
                "commands": [
                    {"path": "map_install_package/RUN.bat", "purpose": "run_application", "commands": ["python app.py"]},
                    {"path": "RUN.bat", "purpose": "run_application", "commands": ["python app.py"]},
                ]
            },
        }
    )

    assert "Project Map Report" in result["markdown"]
    assert {risk["code"] for risk in result["risks"]} >= {"large_artifacts", "risky_imports"}
    assert result["answers"]["1_scope"]["test_surface"]["test_functions"] == 2
    assert "app.py" in result["answers"]["1_scope"]["code_areas"]["core_logic"]
    assert "map_install_package/app.py" not in result["answers"]["1_scope"]["code_areas"]["core_logic"]
    assert "ValueError" in result["answers"]["5_errors_state_repro"]["error_details"]["raises"]
    readiness = result["answers"]["6_runtime_extraction_readiness"]
    execution = result["answers"]["2_execution"]
    assert result["answers"]["3_capabilities"]["pure_transforms"][0]["path"] == "app.py"
    assert result["answers"]["3_capabilities"]["atomic_reusable_capabilities"][0] == "app.py:normalize"
    assert execution["runtime_commands"][0]["path"] == "RUN.bat"
    assert execution["central_flow_nodes"][0]["path"] == "app.py"
    assert "map_install_package/RUN.bat" not in result["markdown"]
    assert "_project_analyzer_extract.py:check_python_syntax" not in [
        row["capability"] for row in readiness["minimal_extraction_plan"]["capabilities_to_extract"]
    ]
    assert readiness["source_strata"]["legacy_noise"][0]["path"] == "_project_analyzer_extract.py"
    assert readiness["source_strata"]["packaged_copy"][0]["path"] == "map_install_package/app.py"
    assert readiness["mixed_responsibility_functions"][0]["name"] == "index"
    assert readiness["idempotency_risks"][0]["target"] == "app.py:index"
    assert readiness["minimal_extraction_plan"]["capabilities_to_extract"][0]["capability"] == "app.py:normalize"
    assert readiness["dataflows"][0]["entrypoint"] == "app.py:index"
    assert readiness["evidence_claims"][0]["evidence"]


def test_project_map_report_flags_snapshot_copy_and_artifact_noise():
    result = run(
        {
            "tree": {
                "root": "F:/ubuntu/VAAT-v4",
                "counts": {"files": 8, "directories": 5, "truncated": False},
                "files": [
                    {"path": "README.md"},
                    {"path": ".env"},
                    {"path": "api/main.py"},
                    {"path": "vaat-v4_20250828/README.md"},
                    {"path": "vaat-v4_20250828/api/main.py"},
                    {"path": "vaat-v4_20250828/.env"},
                    {"path": "vaat-v4_20250828.zip"},
                    {"path": "logs/run.jsonl"},
                    {"path": "notebooks/exploration.ipynb"},
                ],
                "directories": ["api", "vaat-v4_20250828", "vaat-v4_20250828/api", "logs", "notebooks"],
            },
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": ["FastAPI"],
                "entrypoints": ["api/main.py", "vaat-v4_20250828/api/main.py"],
                "large_artifacts": [],
                "dependency_files": [{"path": "requirements.txt", "dependencies": ["fastapi>=0.1"]}],
            },
            "files": {
                "files": [
                    {"path": "README.md", "text": "# VAAT v4\nA2A agents consensus orchestrator"},
                    {"path": ".env", "text": "SECRET_KEY=demo"},
                ]
            },
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [
                    {"path": "api/main.py", "functions": [{"path": "api/main.py", "name": "_execute_pipeline_background", "loc": 40}]},
                    {
                        "path": "vaat-v4_20250828/api/main.py",
                        "functions": [{"path": "vaat-v4_20250828/api/main.py", "name": "_execute_pipeline_background", "loc": 40}],
                    },
                ],
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

    health = result["source_health"]
    risks = {risk["code"] for risk in result["risks"]}
    strata = result["answers"]["6_runtime_extraction_readiness"]["source_strata"]
    assert health["status"] == "noisy"
    assert health["project_shape"] == "dirty_portfolio"
    assert health["packaged_copy_signal_count"] > 0
    assert health["artifact_noise_signal_count"] > 0
    assert "notebooks/exploration.ipynb" in health["artifact_noise_samples"]
    assert health["env_file_signal_count"] > 0
    assert {"packaged_copy_detected", "artifact_noise_detected", "env_file_in_project_tree"} <= risks
    assert any(row["path"] == "vaat-v4_20250828/api/main.py" for row in strata["packaged_copy"])
    assert not any(row["path"] == "vaat-v4_20250828/api/main.py" for row in strata["active_core"])


def test_project_map_report_identifies_ml_competition_workspace_and_hf_token():
    result = run(
        {
            "tree": {
                "root": "F:/ubuntu/zindi.africa.vscode",
                "counts": {"files": 6, "directories": 1, "truncated": False},
                "files": [
                    {"path": "x31.py", "extension": ".py", "size_bytes": 3000},
                    {"path": "auto_install_imports.py", "extension": ".py", "size_bytes": 1200},
                    {"path": "prompts.csv", "extension": ".csv", "size_bytes": 1000},
                    {"path": "data/faiss_index.bin", "extension": ".bin", "size_bytes": 2000},
                    {"path": "data/index_mapping.pkl", "extension": ".pkl", "size_bytes": 2000},
                    {"path": "data/synthetic_2000.jsonl", "extension": ".jsonl", "size_bytes": 2000},
                ],
            },
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": [], "large_artifacts": [], "dependency_files": []},
            "files": {
                "files": [
                    {
                        "path": "x31.py",
                        "text": "from transformers import AutoModelForCausalLM, AutoTokenizer\nmodel.generate(...)\nuse_auth_token='hf_demo_token'\nPROMPT_FILE='prompts.csv'\nOUTPUT_FILE='local_submission.csv'",
                    },
                    {"path": "auto_install_imports.py", "text": "import subprocess\n"},
                ]
            },
            "python_structure": {
                "imports": ["pandas", "numpy", "torch", "transformers", "subprocess"],
                "routes": [],
                "files": [
                    {
                        "path": "x31.py",
                        "functions": [
                            {"path": "x31.py", "name": "generate_response", "line": 1, "loc": 8, "calls": ["model.generate"], "side_effects": []},
                            {"path": "x31.py", "name": "postprocess", "line": 10, "loc": 5, "calls": [], "side_effects": []},
                        ],
                    }
                ],
                "central_nodes": [{"path": "x31.py", "name": "generate_response", "line": 1, "loc": 8, "call_count": 4}],
                "wide_functions": [],
                "pure_transform_candidates": [{"path": "x31.py", "name": "postprocess", "line": 10, "loc": 5}],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
            },
            "runtime_commands": {"commands": []},
        }
    )

    assert result["answers"]["1_scope"]["domain_profile"]["kind"] == "ml_competition_inference_script"
    assert result["security_health"]["status"] == "attention_required"
    assert result["source_health"]["artifact_noise_signal_count"] >= 3
    risks = {risk["code"] for risk in result["risks"]}
    assert "secret_material_in_source" in risks
    assert "artifact_noise_detected" in risks
    assert "submission CSV rows" in result["answers"]["1_scope"]["outputs"]


def test_project_map_report_infers_library_entrypoint_and_demotes_dev_context():
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 4, "directories": 2, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": [], "large_artifacts": [], "dependency_files": []},
            "files": {"files": []},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [
                    {"path": "src/pkg/__init__.py", "functions": []},
                    {"path": "src/pkg/core.py", "functions": []},
                    {"path": "noxfile.py", "functions": []},
                    {"path": "benchmarks/perf.py", "functions": []},
                    {"path": "failures-to-investigate/debug_case.py", "functions": []},
                    {"path": "packaging/pep517_backend/_backend.py", "functions": []},
                    {"path": "scripts/release.py", "functions": []},
                    {"path": "src/pkg/testclient.py", "functions": []},
                ],
                "central_nodes": [],
                "wide_functions": [],
                "pure_transform_candidates": [
                    {"path": "noxfile.py", "name": "session", "line": 1, "loc": 5},
                    {"path": "src/pkg/core.py", "name": "normalize", "line": 1, "loc": 5},
                    {"path": "src/pkg/testclient.py", "name": "handle_request", "line": 1, "loc": 5},
                ],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
            },
            "runtime_commands": {"commands": []},
        }
    )

    readiness = result["answers"]["6_runtime_extraction_readiness"]
    assert result["summary"]["entrypoints"] == ["src/pkg/__init__.py"]
    assert readiness["source_strata"]["active_core"][0]["path"] == "src/pkg/__init__.py"
    assert {row["path"] for row in readiness["source_strata"]["context_only"]} >= {
        "benchmarks/perf.py",
        "failures-to-investigate/debug_case.py",
        "noxfile.py",
        "packaging/pep517_backend/_backend.py",
        "scripts/release.py",
        "src/pkg/testclient.py",
    }
    assert readiness["minimal_extraction_plan"]["capabilities_to_extract"][0]["capability"] == "src/pkg/core.py:normalize"


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
