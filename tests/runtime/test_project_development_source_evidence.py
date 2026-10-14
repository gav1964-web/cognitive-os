from __future__ import annotations

from runtime.project_development_source_evidence import (
    collect_python_target_facts,
    collect_source_incompleteness_evidence,
)


def test_target_facts_find_function_below_module_feature_guard(tmp_path):
    source = tmp_path / "src" / "plugin.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "have_optional = True\n\n"
        "if have_optional:\n"
        "    def seed_fixture(config):\n"
        "        return config.getoption('seed') + 1\n",
        encoding="utf-8",
    )

    facts = collect_python_target_facts(tmp_path, "src/plugin.py:seed_fixture")

    assert facts["source_backed"] is True
    assert facts["symbol"] == "seed_fixture"
    assert facts["line_start"] == 4


def test_target_facts_characterize_exception_pickle_constructor_shape(tmp_path):
    (tmp_path / "errors.py").write_text(
        "class DirectError(RuntimeError):\n"
        "    def __init__(self, message):\n"
        "        super().__init__(message)\n\n"
        "class FormattedError(RuntimeError):\n"
        "    def __init__(self, allowed, host):\n"
        "        message = f'{host}: {allowed}'\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )

    direct = collect_python_target_facts(tmp_path, "errors.py:DirectError.__init__")
    formatted = collect_python_target_facts(tmp_path, "errors.py:FormattedError.__init__")

    assert direct["custom_exception_constructor"] is True
    assert direct["base_exception_replays_constructor_parameters"] is True
    assert formatted["constructor_parameters"] == ["allowed", "host"]
    assert formatted["base_exception_direct_parameters"] == ["message"]
    assert formatted["base_exception_replays_constructor_parameters"] is False
    assert formatted["has_reduce_method"] is False


def test_source_incompleteness_classifier_separates_intentional_shapes(tmp_path):
    (tmp_path / "sample.py").write_text(
        "from abc import ABC, abstractmethod\n\n"
        "class EmptyError(Exception):\n"
        "    pass\n\n"
        "class Port(ABC):\n"
        "    @abstractmethod\n"
        "    def send(self):\n"
        "        raise NotImplementedError\n\n"
        "def close_quietly():\n"
        "    try:\n"
        "        close()\n"
        "    except OSError:\n"
        "        # Deliberately ignore a closed resource.\n"
        "        pass\n",
        encoding="utf-8",
    )

    evidence = collect_source_incompleteness_evidence(tmp_path)
    classes = {row["target"]: row["classification"] for row in evidence["findings"]}

    assert classes["sample.py:EmptyError"] == "intentional_marker_type"
    assert classes["sample.py:Port.send"] == "intentional_interface_boundary"
    assert classes["sample.py:except@14"] == "intentional_exception_suppression"
    assert evidence["status"] == "observations_only"
    assert evidence["actionable_count"] == 0


def test_todo_stub_is_declared_work_but_not_actionable_without_failure(tmp_path):
    (tmp_path / "model.py").write_text(
        "class CustomNode:\n"
        "    # TODO: Add lock-file fields.\n"
        "    pass\n",
        encoding="utf-8",
    )

    evidence = collect_source_incompleteness_evidence(tmp_path)

    assert evidence["findings"][0]["classification"] == "declared_future_work"
    assert evidence["findings"][0]["intent_marker"] == "TODO: Add lock-file fields."
    assert evidence["findings"][0]["actionable"] is False


def test_stub_becomes_actionable_only_with_target_bound_failure(tmp_path):
    (tmp_path / "service.py").write_text("def normalize(value):\n    pass\n", encoding="utf-8")

    evidence = collect_source_incompleteness_evidence(
        tmp_path,
        corroborating_failures=[{
            "target": "service.py:normalize",
            "authority": "failing_contract_test",
            "detail": "test_normalize expected a normalized value",
        }],
    )

    finding = evidence["actionable_findings"][0]
    assert finding["classification"] == "corroborated_incomplete"
    assert finding["authority"] == "failing_contract_test"
    assert evidence["status"] == "actionable"


def test_unapproved_claim_cannot_promote_stub(tmp_path):
    (tmp_path / "service.py").write_text("def normalize(value):\n    pass\n", encoding="utf-8")

    evidence = collect_source_incompleteness_evidence(
        tmp_path,
        corroborating_failures=[{
            "target": "service.py:normalize",
            "authority": "source_incompleteness",
        }],
    )

    assert evidence["actionable_count"] == 0
    assert evidence["findings"][0]["classification"] == "ambiguous_stub"


def test_test_fixture_stubs_do_not_consume_production_evidence_budget(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "fixture.py").write_text("def fake():\n    pass\n", encoding="utf-8")
    (tmp_path / "service.py").write_text("def real_stub():\n    pass\n", encoding="utf-8")

    evidence = collect_source_incompleteness_evidence(tmp_path)

    assert [row["target"] for row in evidence["findings"]] == ["service.py:real_stub"]
    assert evidence["files_scanned"] == 1
