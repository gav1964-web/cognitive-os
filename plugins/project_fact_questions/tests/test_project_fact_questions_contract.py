from plugins.project_fact_questions.src.main import run


def test_project_fact_questions_answers_static_file_questions():
    result = run(
        {
            "tree": {
                "files": [
                    {"path": "app.py", "extension": ".py", "line_count": 301},
                    {"path": "small.py", "extension": ".py", "line_count": 12},
                    {"path": "README.md", "extension": ".md", "line_count": 50},
                ]
            },
            "python_structure": {
                "files": [
                    {
                        "path": "app.py",
                        "imports": ["cv2", "pathlib"],
                        "functions": [{"name": "load", "side_effects": ["filesystem_read"]}],
                    },
                    {
                        "path": "small.py",
                        "imports": [],
                        "functions": [{"name": "pure", "side_effects": []}],
                    },
                ]
            },
            "questions": [],
        }
    )

    answers = result["answers"]
    assert answers["py_files_over_300_lines"]["count"] == 1
    assert answers["py_files_over_300_lines"]["files"][0]["path"] == "app.py"
    assert answers["opencv_usage"]["files"] == [{"path": "app.py", "evidence": ["import:cv2"]}]
    assert answers["disk_work"]["files"][0]["path"] == "app.py"


def test_project_fact_questions_can_scope_to_active_core():
    result = run(
        {
            "tree": {
                "files": [
                    {"path": "app.py", "extension": ".py", "line_count": 301},
                    {"path": "build/generated.py", "extension": ".py", "line_count": 999},
                ]
            },
            "python_structure": {
                "files": [
                    {
                        "path": "app.py",
                        "imports": ["cv2", "pathlib"],
                        "functions": [{"name": "load", "side_effects": ["filesystem_read"]}],
                    },
                    {
                        "path": "build/generated.py",
                        "imports": ["cv2", "os"],
                        "functions": [{"name": "write", "side_effects": ["filesystem"]}],
                    },
                ]
            },
            "project_map_report": {
                "answers": {
                    "6_runtime_extraction_readiness": {
                        "source_strata": {
                            "active_core": [{"path": "app.py", "kind": "active_core"}],
                            "context_only": [{"path": "build/generated.py", "kind": "context_only"}],
                        }
                    }
                }
            },
            "scope": "active_core",
            "questions": [],
        }
    )

    answers = result["answers"]
    assert result["scope"] == "active_core"
    assert answers["py_files_over_300_lines"]["files"] == [{"path": "app.py", "line_count": 301}]
    assert answers["opencv_usage"]["files"] == [{"path": "app.py", "evidence": ["import:cv2"]}]
    assert [row["path"] for row in answers["disk_work"]["files"]] == ["app.py"]
