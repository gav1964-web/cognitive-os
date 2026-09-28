from runtime.source_scope_field_trial import run_source_scope_field_trial


def test_source_scope_trial_separates_production_and_test_risk(tmp_path):
    corpus = tmp_path / "corpus"
    project = corpus / "project-a"
    tests = project / "tests"
    tests.mkdir(parents=True)
    app = project / "app"
    app.mkdir()
    (project / "render.py").write_text(
        "def render():\n    def value():\n        return 1\n    savefig('out.png')\n",
        encoding="utf-8",
    )
    (tests / "test_render.py").write_text(
        "def test_render():\n    def fake():\n        return 1\n",
        encoding="utf-8",
    )
    (app / "tests.py").write_text(
        "def test_handler():\n    def fake():\n        return 1\n",
        encoding="utf-8",
    )
    (project / "valid.py").write_text(
        "def outer():\n    def nested():\n        return 1\n    return nested()\n",
        encoding="utf-8",
    )

    report = run_source_scope_field_trial(corpus_dir=corpus)

    assert report["status"] == "ok"
    assert report["summary"]["functions_with_nested_scopes"] == 4
    assert report["summary"]["return_path_inflation"] == 4
    assert report["summary"]["false_nonvoid_risk"] == 3
    assert report["summary"]["false_nonvoid_production"] == 1
    assert report["summary"]["false_nonvoid_test"] == 2
    assert report["summary"]["savefig_scopes"] == 1
    assert report["summary"]["savefig_production"] == 1
    assert report["summary"]["affected_projects"] == 1
    assert report["conclusion"] == "scope_aware_ast_required"
