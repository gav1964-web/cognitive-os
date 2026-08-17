from plugins.project_map_report.src.language_scope import language_scope, load_language_scope_policy


def test_typescript_monorepo_limits_python_analysis_scope():
    scope = language_scope(
        {
            "languages": [
                {"language": ".ts", "files": 2309},
                {"language": ".tsx", "files": 259},
                {"language": "Python", "files": 18},
            ]
        }
    )

    assert scope["status"] == "limited"
    assert scope["primary_language"] == "TypeScript"
    assert scope["analyzed_boundary"] == "python_subproject_only"


def test_python_owned_project_keeps_full_scope():
    scope = language_scope({"languages": [{"language": "Python", "files": 40}, {"language": ".ts", "files": 3}]})

    assert scope["status"] == "full"
    assert load_language_scope_policy()["provenance"]["source"]
