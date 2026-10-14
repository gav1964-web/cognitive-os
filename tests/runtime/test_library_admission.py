from pathlib import Path

import pytest

from runtime.library_admission import inspect_library_admission


def library(root: Path):
    (root / "pyproject.toml").write_text("[project]\nname='neutral-name'\n", encoding="utf-8")
    (root / "demo.py").write_text("def normalize(value): return value.strip().lower()\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/test_demo.py").write_text("from demo import normalize\ndef test_normalize(): assert normalize(' A ') == 'a'\n", encoding="utf-8")


def test_source_backed_library_without_name_keywords_is_admitted(tmp_path):
    library(tmp_path)
    result = inspect_library_admission(tmp_path)
    assert result["status"] == "admitted_candidate"
    assert result["test_api_links"][0]["symbol"] == "demo.normalize"
    assert set(result["source_sha256"]) == {"pyproject.toml", "demo.py", "tests/test_demo.py"}


def test_readme_only_template_cannot_qualify(tmp_path):
    (tmp_path / "README.md").write_text("Parser schema validation library", encoding="utf-8")
    assert inspect_library_admission(tmp_path)["status"] == "rejected"


@pytest.mark.parametrize("content", ["def test_nothing(): assert True\n",
                                     "from demo import normalize\ndef test_nothing(): assert True\n",
                                     "from demo import other\ndef test_other(): assert other('x') == 'x'\n"])
def test_tests_must_call_an_owned_transform_candidate(tmp_path, content):
    library(tmp_path)
    (tmp_path / "tests/test_demo.py").write_text(content, encoding="utf-8")
    assert "tests_exercise_owned_api" in inspect_library_admission(tmp_path)["failed_checks"]


def test_framework_import_in_source_blocks_application(tmp_path):
    library(tmp_path)
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n", encoding="utf-8")
    assert "no_application_framework_imports" in inspect_library_admission(tmp_path)["failed_checks"]


def test_direct_io_is_not_a_transform_candidate(tmp_path):
    library(tmp_path)
    (tmp_path / "demo.py").write_text("def normalize(value): return open(value).read()\n", encoding="utf-8")
    assert "public_transform_candidates" in inspect_library_admission(tmp_path)["failed_checks"]


def test_setup_py_is_never_executed(tmp_path):
    (tmp_path / "setup.py").write_text("raise RuntimeError('do not execute')\nfrom setuptools import setup\nsetup(name='safe')\n", encoding="utf-8")
    result = inspect_library_admission(tmp_path)
    assert result["package"]["name"] == "safe"
    assert result["status"] == "rejected"


def test_source_changes_change_admission_digest(tmp_path):
    library(tmp_path)
    before = inspect_library_admission(tmp_path)["evidence_digest"]
    (tmp_path / "demo.py").write_text("def normalize(value): return value.lower()\n", encoding="utf-8")
    assert inspect_library_admission(tmp_path)["evidence_digest"] != before


def test_oversized_or_invalid_metadata_fails_closed(tmp_path):
    (tmp_path / "pyproject.toml").write_text("invalid toml", encoding="utf-8")
    assert inspect_library_admission(tmp_path)["errors"]
