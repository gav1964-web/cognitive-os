from plugins.project_map_report.src.main import run


def test_vendored_syntax_errors_are_noise_not_active_source_damage():
    result = run(
        {
            "tree": {
                "root": "invoke",
                "counts": {"files": 20, "directories": 6, "truncated": False},
                "files": [{"path": "invoke/parser/context.py"}],
                "skipped": {},
            },
            "stack": {
                "languages": [{"language": "Python"}],
                "frameworks": [],
                "entrypoints": [],
                "large_artifacts": [],
                "dependency_files": [{"path": "setup.py", "dependencies": []}],
            },
            "files": {"files": [], "skipped": []},
            "python_structure": {
                "imports": [],
                "routes": [],
                "files": [{"path": "invoke/parser/context.py", "functions": []}],
                "central_nodes": [],
                "wide_functions": [],
                "pure_transform_candidates": [],
                "project_insights": {},
                "contracts": {},
                "external_dependencies": {},
                "skipped": [
                    {"path": "invoke/vendor/yaml3/parser.py", "reason": "SyntaxError"}
                ],
            },
            "runtime_commands": {"commands": [], "skipped": []},
        }
    )

    health = result["source_health"]
    assert health["status"] == "noisy"
    assert health["syntax_error_count"] == 0
    assert health["vendored_syntax_error_count"] == 1
    assert "exclude vendored parser-incompatible source" in health["recommendation"]
