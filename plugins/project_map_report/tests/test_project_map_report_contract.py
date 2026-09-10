from plugins.project_map_report.src.main import run
from plugins.project_map_report.src.runtime_readiness import resume_reuse_plan


def test_runtime_readiness_preserves_resume_plan_compatibility_export():
    assert callable(resume_reuse_plan)


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
    assert result["human_summary"]["purpose"]
    assert result["evidence_summary"]["source_refs"]
    assert result["evidence_summary"]["limits"]
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
    assert health["noise_exclusion_decision"]["status"] in {"context_only_noise_excluded", "pending_active_root"}
    assert health["noise_exclusion_decision"]["excluded_signal_count"] > 0
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


def test_project_map_report_combines_stack_and_package_entrypoints():
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 3, "directories": 1, "truncated": False}},
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": ["app.py"],
                "large_artifacts": [],
                "dependency_files": [],
            },
            "files": {"files": [{"path": "README.md", "text": "# Demo\n\nReusable package."}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "pkg/__init__.py", "functions": []}],
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

    assert result["summary"]["entrypoints"] == ["app.py", "pkg/__init__.py"]
