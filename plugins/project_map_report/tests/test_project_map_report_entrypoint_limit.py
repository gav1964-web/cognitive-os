from __future__ import annotations

from plugins.project_map_report.src.main import run


def test_project_map_report_keeps_more_than_eight_combined_entrypoints():
    files = [{"path": f"src/pkg/part_{index}/__init__.py", "functions": []} for index in range(20)]
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 21, "directories": 20, "truncated": False}},
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": ["src/pkg/cli/main.py"],
                "large_artifacts": [],
                "dependency_files": [],
            },
            "files": {"files": [{"path": "README.md", "text": "# Demo\n\nReusable package."}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": files,
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

    assert len(result["summary"]["entrypoints"]) == 21
    assert "src/pkg/part_19/__init__.py" in result["summary"]["entrypoints"]


def test_project_map_report_detects_lib_and_nested_src_package_entrypoints():
    files = [
        {"path": "lib/sqlalchemy/__init__.py", "functions": []},
        {"path": "opentelemetry-api/src/opentelemetry/__init__.py", "functions": []},
    ]
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 2, "directories": 2, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": []},
            "files": {"files": [{"path": "README.md", "text": "# Demo\n\nReusable package."}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": files,
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

    assert result["summary"]["entrypoints"] == [
        "lib/sqlalchemy/__init__.py",
        "opentelemetry-api/src/opentelemetry/__init__.py",
    ]


def test_project_map_report_uses_top_level_module_when_no_package_entrypoint():
    result = run(
        {
            "tree": {"root": "single-file-library", "counts": {"files": 3, "directories": 0, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": []},
            "files": {"files": [{"path": "README.md", "text": "# Tool\n\nSingle module library."}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [
                    {"path": "pycodestyle.py", "functions": [{"path": "pycodestyle.py", "name": "main", "loc": 20}]},
                    {"path": "setup.py", "functions": []},
                    {"path": "test_pycodestyle.py", "functions": []},
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

    assert result["summary"]["entrypoints"] == ["pycodestyle.py"]


def test_project_map_report_keeps_library_package_entrypoints_without_stack_entrypoints():
    files = [{"path": f"src/pkg/area_{index}/__init__.py", "functions": []} for index in range(24)]
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 24, "directories": 24, "truncated": False}},
            "stack": {"languages": [{"language": "Python"}], "frameworks": [], "entrypoints": []},
            "files": {"files": [{"path": "README.md", "text": "# Demo\n\nReusable package."}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": files,
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

    assert len(result["summary"]["entrypoints"]) == 24
    assert "src/pkg/area_23/__init__.py" in result["summary"]["entrypoints"]


def test_project_map_report_filters_context_only_stack_entrypoints():
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 2, "directories": 2, "truncated": False}},
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": ["docs_src/tutorial/main.py", "src/pkg/__init__.py"],
                "large_artifacts": [],
                "dependency_files": [],
            },
            "files": {"files": [{"path": "README.md", "text": "# Demo\n\nReusable package."}]},
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

    assert result["summary"]["entrypoints"] == ["src/pkg/__init__.py"]


def test_project_map_report_filters_test_runner_stack_entrypoints():
    result = run(
        {
            "tree": {"root": "library", "counts": {"files": 2, "directories": 2, "truncated": False}},
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": ["pydantic-core/wasm-preview/run_tests.py", "pydantic/__init__.py"],
                "large_artifacts": [],
                "dependency_files": [],
            },
            "files": {"files": [{"path": "README.md", "text": "# Demo\n\nReusable package."}]},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "pydantic/__init__.py", "functions": []}],
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

    assert result["summary"]["entrypoints"] == ["pydantic/__init__.py"]
