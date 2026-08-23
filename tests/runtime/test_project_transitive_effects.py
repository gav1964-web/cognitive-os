from runtime.project_transitive_effects import project_transitive_effects


def test_project_effects_follow_unique_cross_file_calls(tmp_path):
    (tmp_path / "service.py").write_text(
        "def publish(payload):\n    requests.post('/events', json=payload)\n",
        encoding="utf-8",
    )
    (tmp_path / "signals.py").write_text(
        "from service import publish\n\ndef on_task_postrun(payload):\n    publish(payload)\n",
        encoding="utf-8",
    )

    report = project_transitive_effects(tmp_path)

    row = report["signals.py:on_task_postrun"]
    assert row["transitive_side_effects"] == ["network"]
    assert row["contract_slice_sources"] == ["service.py:publish", "signals.py:on_task_postrun"]


def test_project_effects_do_not_guess_ambiguous_symbols(tmp_path):
    (tmp_path / "a.py").write_text("def publish(value):\n    open('a', 'w').write(value)\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def publish(value):\n    open('b', 'w').write(value)\n", encoding="utf-8")
    (tmp_path / "caller.py").write_text("def run(value):\n    publish(value)\n", encoding="utf-8")

    report = project_transitive_effects(tmp_path)

    assert report["caller.py:run"] == {}


def test_project_effects_do_not_resolve_attribute_calls_by_suffix(tmp_path):
    (tmp_path / "service.py").write_text(
        "def post(payload):\n    open('events.log', 'w').write(payload)\n",
        encoding="utf-8",
    )
    (tmp_path / "client.py").write_text(
        "def send(client, payload):\n    return client.post(payload)\n",
        encoding="utf-8",
    )

    report = project_transitive_effects(tmp_path)

    assert report["client.py:send"] == {}


def test_project_effects_do_not_depend_on_ast_unparse(monkeypatch, tmp_path):
    (tmp_path / "service.py").write_text(
        "def publish(payload):\n    open('events.log', 'w').write(payload)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("runtime.project_transitive_effects.ast.unparse", lambda node: (_ for _ in ()).throw(ValueError("unsupported f-string")))

    report = project_transitive_effects(tmp_path)

    assert report["service.py:publish"] == {}


def test_project_effects_do_not_rescan_full_source_for_each_callable(monkeypatch, tmp_path):
    functions = "\n".join(
        f"def operation_{index}():\n    open('events.log', 'a').write('{index}')\n"
        for index in range(200)
    )
    (tmp_path / "generated.py").write_text(functions, encoding="utf-8")
    monkeypatch.setattr(
        "runtime.project_transitive_effects.ast.get_source_segment",
        lambda *_args: (_ for _ in ()).throw(AssertionError("full-source rescan")),
    )

    report = project_transitive_effects(tmp_path)

    assert len(report) == 200


def test_project_effects_preserve_class_qualified_methods_and_self_calls(tmp_path):
    (tmp_path / "widget.py").write_text(
        "class Widget:\n"
        "    def move(self):\n        self.position = 1\n"
        "    def handle(self):\n        self.move()\n",
        encoding="utf-8",
    )

    report = project_transitive_effects(tmp_path)

    assert report["widget.py:Widget.handle"]["transitive_side_effects"] == ["memory_state"]
    assert "widget.py:Widget.move" in report["widget.py:Widget.handle"]["contract_slice_sources"]
