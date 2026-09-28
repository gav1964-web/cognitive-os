from __future__ import annotations

from pathlib import Path

from runtime.post_split_audit import run_post_split_audit


def test_post_split_audit_reports_facades_and_helper_backed_tests(tmp_path: Path):
    runtime = tmp_path / "runtime"
    tests = tmp_path / "tests" / "runtime"
    runtime.mkdir(parents=True)
    tests.mkdir(parents=True)
    (runtime / "facade.py").write_text(
        '"""Stable facade for split demo."""\n'
        "import importlib\n"
        '_PART_NAMES = ["demo_part1"]\n'
        "_PARTS = [importlib.import_module(name) for name in _PART_NAMES]\n",
        encoding="utf-8",
    )
    (tests / "test_demo.py").write_text(
        "from tests.runtime.demo_helpers import *\n\n"
        "def test_demo():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    report = run_post_split_audit(root=tmp_path)

    assert report["status"] == "ok"
    assert report["facade_count"] == 1
    assert report["helper_backed_test_count"] == 1
    assert report["facades"][0]["path"] == "runtime/facade.py"
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False


def test_post_split_audit_ignores_marker_text_without_executable_facade(tmp_path: Path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_markers.py").write_text(
        'TEXT = "Stable facade for split _PART_NAMES importlib.import_module"\n',
        encoding="utf-8",
    )

    report = run_post_split_audit(root=tmp_path)

    assert report["facade_count"] == 0
