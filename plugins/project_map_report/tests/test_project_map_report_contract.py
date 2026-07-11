from plugins.project_map_report.src.main import run


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
