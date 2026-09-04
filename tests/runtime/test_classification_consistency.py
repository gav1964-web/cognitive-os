from __future__ import annotations

from pathlib import Path

from runtime.classification_consistency import (
    evaluate_classification_consistency,
    load_classification_consistency_policy,
)
from runtime.project_development import (
    build_development_diagnosis,
    build_development_options,
    load_project_development_policy,
    select_development_option,
)


def _provider(root: Path) -> None:
    source = root / "pkg" / "build_meta.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def build_wheel(wheel_directory, **kwargs):\n    return 'x.whl'\n\n"
        "def build_sdist(sdist_directory, **kwargs):\n    return 'x.tar.gz'\n\n"
        "def prepare_metadata_for_build_wheel(metadata_directory, **kwargs):\n    return 'x.dist-info'\n",
        encoding="utf-8",
    )


def _recognition(stratum: str, archetype: str, *, status: str = "recognized") -> dict:
    return {
        "status": status,
        "classification": {
            "project_stratum": stratum,
            "project_archetype": archetype,
        },
        "ambiguity_reasons": [],
    }


def _pytest_plugin(root: Path) -> None:
    (root / "setup.cfg").write_text(
        "[options.entry_points]\npytest11 =\n    sample = sample.plugin\n",
        encoding="utf-8",
    )
    source = root / "sample" / "plugin.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "import pytest\n\n@pytest.fixture\ndef sample_fixture():\n    return 'value'\n",
        encoding="utf-8",
    )


def test_owned_contract_detects_recognized_false_classification(tmp_path: Path) -> None:
    _provider(tmp_path)

    evidence = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=_recognition("library_pure_transform", "configuration_file_parser_library"),
    )

    assert evidence["status"] == "classification_contradiction"
    contradiction = evidence["contradictions"][0]
    assert contradiction["contract_id"] == "owned_packaging_build_backend"
    assert contradiction["mismatched_fields"] == ["project_stratum", "project_archetype"]
    assert evidence["authority"] == "independent_ast_contract_evaluator"


def test_owned_contract_accepts_matching_classification(tmp_path: Path) -> None:
    _provider(tmp_path)

    evidence = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=_recognition("framework_plugin_build", "packaging_build_backend"),
    )

    assert evidence["status"] == "consistent"
    assert evidence["contradictions"] == []


def test_consumer_declaration_is_not_independent_contract(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[build-system]\nbuild-backend="setuptools.build_meta"\n', encoding="utf-8"
    )
    (tmp_path / "consumer.py").write_text("def parse_config(value):\n    return value\n", encoding="utf-8")

    evidence = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=_recognition("library_pure_transform", "configuration_file_parser_library"),
    )

    assert evidence["status"] == "no_independent_contract"
    assert evidence["contracts"] == []


def test_registered_pytest_plugin_is_an_independent_contract(tmp_path: Path) -> None:
    _pytest_plugin(tmp_path)

    evidence = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=_recognition("framework_plugin_build", "pytest_plugin"),
    )

    assert evidence["status"] == "consistent"
    assert evidence["contracts"][0]["contract_id"] == "owned_pytest_plugin"
    assert evidence["contracts"][0]["evidence"][0]["decorator_hits"] == ["pytest.fixture"]


def test_test_local_pytest_fixture_is_not_an_owned_plugin(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text(
        "import pytest\n\n@pytest.fixture\ndef sample_fixture():\n    return 'value'\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project.optional-dependencies]\ntest = ['pytest']\n", encoding="utf-8"
    )

    evidence = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=_recognition("library_pure_transform", "python_transform_library"),
    )

    assert evidence["status"] == "no_independent_contract"


def test_registered_package_hook_is_an_owned_plugin_contract(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project.entry-points.pytest11]\nsample = 'sample'\n", encoding="utf-8"
    )
    source = tmp_path / "src" / "sample" / "__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text("def pytest_addoption(parser):\n    return None\n", encoding="utf-8")

    evidence = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=_recognition("framework_plugin_build", "pytest_plugin"),
    )

    assert evidence["status"] == "consistent"
    row = evidence["contracts"][0]["evidence"][0]
    assert row["path"] == "src/sample/__init__.py"
    assert row["function_prefix_hits"] == ["pytest_addoption"]


def test_contradiction_becomes_research_only_development_issue(tmp_path: Path) -> None:
    _provider(tmp_path)
    recognition = _recognition("library_pure_transform", "configuration_file_parser_library")
    consistency = evaluate_classification_consistency(
        project_dir=tmp_path,
        recognition=recognition,
    )
    policy = load_project_development_policy()

    diagnosis = build_development_diagnosis(
        project="provider",
        project_report={"source_health": {"status": "clean", "project_shape": "single_project"}, "risks": [], "answers": {}},
        recognition=recognition,
        classification_consistency=consistency,
        policy=policy,
    )
    portfolio = build_development_options(diagnosis, policy=policy)
    decision = select_development_option(diagnosis, portfolio, policy=policy)

    issue = next(row for row in diagnosis["issues"] if row["rule_id"] == "classification_contradiction")
    assert issue["subject"] == "owned_contract_vs_project_identity"
    assert issue["affected_targets"] == ["pkg/build_meta.py"]
    assert decision["selected_option"]["route"] == "research"


def test_current_policy_is_fail_closed() -> None:
    policy = load_classification_consistency_policy()

    assert policy["invariants"]["independent_from_matcher_result"] is True
    assert policy["invariants"]["promotion_applied"] is False
