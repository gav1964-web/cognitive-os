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


def test_project_fact_questions_uses_line_threshold_from_question():
    result = run(
        {
            "tree": {
                "files": [
                    {"path": "large.py", "extension": ".py", "line_count": 301},
                    {"path": "medium.py", "extension": ".py", "line_count": 251},
                    {"path": "small.py", "extension": ".py", "line_count": 250},
                ]
            },
            "python_structure": {"files": []},
            "questions": ["дай список файлов .py больше 250 строк"],
        }
    )

    answers = result["answers"]
    assert answers["py_files_over_250_lines"]["threshold"] == 250
    assert answers["py_files_over_250_lines"]["query_spec"]["artifact_type"] == "ProjectFactQuerySpec"
    assert answers["py_files_over_250_lines"]["query_spec"]["pattern_id"] == "py_files_over_lines"
    assert [row["path"] for row in answers["py_files_over_250_lines"]["files"]] == ["large.py", "medium.py"]
    assert result["selected_answers"][0]["answer_key"] == "py_files_over_250_lines"


def test_project_fact_questions_uses_file_size_threshold_from_question():
    result = run(
        {
            "tree": {
                "files": [
                    {"path": "big.json", "extension": ".json", "size_bytes": 25 * 1024},
                    {"path": "medium.py", "extension": ".py", "size_bytes": 20 * 1024 + 1, "line_count": 20},
                    {"path": "small.md", "extension": ".md", "size_bytes": 20 * 1024},
                ]
            },
            "python_structure": {"files": []},
            "questions": ["дай список файлов больше 20 kb"],
        }
    )

    answers = result["answers"]
    answer = answers["files_over_20_kb"]
    assert answer["threshold_bytes"] == 20 * 1024
    assert answer["query_spec"]["artifact_type"] == "ProjectFactQuerySpec"
    assert answer["query_spec"]["pattern_id"] == "files_over_size"
    assert [row["path"] for row in answer["files"]] == ["big.json", "medium.py"]
    assert result["selected_answers"][0]["answer_key"] == "files_over_20_kb"


def test_project_fact_questions_can_query_filenames_with_underscore_top_by_size():
    result = run(
        {
            "tree": {
                "files": [
                    {"path": "a/no_1.py", "extension": ".py", "size_bytes": 10},
                    {"path": "b/huge_file.json", "extension": ".json", "size_bytes": 5000},
                    {"path": "plain.txt", "extension": ".txt", "size_bytes": 9999},
                    {"path": "c/mid_file.md", "extension": ".md", "size_bytes": 1000},
                ]
            },
            "python_structure": {"files": []},
            "questions": ["в каких именах файлов есть подчеркивание - выведи топ 10 по размеру"],
        }
    )

    selected = result["selected_answers"][0]
    assert selected["answer_key"] == "files_name_contains_underscore_top_10_by_size_bytes_desc"
    assert selected["answer"]["query_spec"]["artifact_type"] == "ProjectFactQuerySpec"
    assert selected["answer"]["query_spec"]["pattern_id"] == "files_name_contains_underscore_top_by_size"
    assert [row["path"] for row in selected["answer"]["files"]] == [
        "b/huge_file.json",
        "c/mid_file.md",
        "a/no_1.py",
    ]
    assert selected["answer"]["count_total"] == 3


def test_project_fact_questions_can_query_function_names_by_token():
    result = run(
        {
            "tree": {"files": []},
            "python_structure": {
                "files": [
                    {
                        "path": "app/files.py",
                        "functions": [
                            {"name": "read_file", "line": 10, "loc": 5},
                            {"name": "write_file_report", "line": 30, "loc": 7},
                        ],
                    },
                    {
                        "path": "app/users.py",
                        "functions": [{"name": "create_user", "line": 8, "loc": 4}],
                    },
                    {
                        "path": "app/upload.py",
                        "functions": [{"name": "FileUploadHandler", "line": 14, "loc": 12}],
                    },
                ]
            },
            "questions": ["в каких файлах содержится слово file в названии функции"],
        }
    )

    selected = result["selected_answers"][0]
    assert selected["answer_key"] == "functions_name_contains_file"
    assert selected["answer"]["query_spec"]["artifact_type"] == "ProjectSymbolQuerySpec"
    assert selected["answer"]["query_spec"]["pattern_id"] == "functions_name_contains_token"
    assert selected["answer"]["count_files"] == 2
    assert [row["path"] for row in selected["answer"]["files"]] == ["app/files.py", "app/upload.py"]
    assert [row["name"] for row in selected["answer"]["files"][0]["functions"]] == [
        "read_file",
        "write_file_report",
    ]


def test_project_fact_questions_can_add_function_purpose_summaries():
    result = run(
        {
            "tree": {"files": []},
            "python_structure": {
                "files": [
                    {
                        "path": "scratch/sync_to_drive.py",
                        "functions": [
                            {
                                "name": "upload_file_task",
                                "line": 264,
                                "loc": 34,
                                "calls": ["service.files.create", "execute"],
                                "side_effects": ["network"],
                            }
                        ],
                    }
                ]
            },
            "questions": [
                "в каких файлах содержится слово file в названии функции и для чего эти функции предназначены - краткое саммари по каждому случаю"
            ],
        }
    )

    selected = result["selected_answers"][0]
    function = selected["answer"]["files"][0]["functions"][0]
    assert selected["answer_key"] == "functions_name_contains_file"
    assert selected["answer"]["query_spec"]["include_purpose_summary"] is True
    assert "purpose_summary" in function
    assert "работает с файлом" in function["purpose_summary"]
    assert "вызывает: service.files.create, execute" in function["purpose_summary"]


def test_project_fact_questions_can_return_function_source_by_name_and_path(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_config_loading.py").write_text(
        "\n".join(
            [
                "def helper():",
                "    return 1",
                "",
                "def test_loads_routing_profiles_and_aliases():",
                "    config = load_config()",
                "    assert config.routing_profiles",
            ]
        ),
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {"root": str(tmp_path), "files": []},
            "python_structure": {
                "root": str(tmp_path),
                "files": [
                    {
                        "path": "tests/test_config_loading.py",
                        "functions": [
                            {"name": "helper", "line": 1, "end_line": 2, "loc": 2},
                            {
                                "name": "test_loads_routing_profiles_and_aliases",
                                "line": 4,
                                "end_line": 6,
                                "loc": 3,
                            },
                        ],
                    }
                ],
            },
            "questions": [
                "выведи на печать текст функции test_loads_routing_profiles_and_aliases из tests/test_config_loading.py"
            ],
        }
    )

    selected = result["selected_answers"][0]
    source = selected["answer"]["files"][0]["functions"][0]["source"]
    assert selected["answer_key"] == "function_source_test_loads_routing_profiles_and_aliases"
    assert selected["answer"]["query_spec"]["pattern_id"] == "function_source_by_name_and_path"
    assert source["status"] == "found"
    assert source["start_line"] == 4
    assert "def test_loads_routing_profiles_and_aliases():" in source["text"]
    assert "assert config.routing_profiles" in source["text"]


def test_project_fact_questions_can_explain_call_occurrences_inside_function(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_config_loading.py").write_text(
        "\n".join(
            [
                "def test_loads_routing_profiles_and_aliases(tmp_path, monkeypatch):",
                "    monkeypatch.setenv(\"DEEPSEEK_API_KEY\", \"test-key\")",
                "    monkeypatch.setenv(\"GOOGLE_CREDENTIALS_FILE\", str(tmp_path))",
                "    cfg = load_config()",
            ]
        ),
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {"root": str(tmp_path), "files": []},
            "python_structure": {
                "root": str(tmp_path),
                "files": [
                    {
                        "path": "tests/test_config_loading.py",
                        "functions": [
                            {
                                "name": "test_loads_routing_profiles_and_aliases",
                                "line": 1,
                                "end_line": 4,
                                "loc": 4,
                            }
                        ],
                    }
                ],
            },
            "questions": [
                "что делает функция monkeypatch.setenv( в функции test_loads_routing_profiles_and_aliases из tests/test_config_loading.py и почему она встречается дважды"
            ],
        }
    )

    selected = result["selected_answers"][0]
    explanation = selected["answer"]["files"][0]["functions"][0]["call_explanation"]
    assert selected["answer"]["query_spec"]["pattern_id"] == "function_call_explanation_by_name_path_and_call"
    assert explanation["call_target"] == "monkeypatch.setenv"
    assert explanation["occurrence_count"] == 2
    assert "временно задает переменную окружения" in explanation["summary"]
    assert "DEEPSEEK_API_KEY" in explanation["why_repeated"]
    assert "GOOGLE_CREDENTIALS_FILE" in explanation["why_repeated"]


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


def test_project_fact_questions_answers_client_connection_port(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "USAGE.md").write_text(
        "Run clients against --base-url http://localhost:8000/v1\n",
        encoding="utf-8",
    )
    result = run(
        {
            "tree": {
                "root": str(tmp_path),
                "files": [{"path": "docs/USAGE.md", "line_count": 1}],
            },
            "python_structure": {"root": str(tmp_path), "files": [], "imports": []},
            "questions": ["какой порт используется для подключения клиентов"],
        }
    )

    answer = result["answers"]["client_connection_port"]
    assert answer["status"] == "found"
    assert answer["port"] == 8000
    assert answer["evidence"][0]["path"] == "docs/USAGE.md"
