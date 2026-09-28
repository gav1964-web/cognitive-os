from pathlib import Path

import pytest

from runtime.project_native_failure_binding import _interpret_pytest_result


def project(tmp_path, test_body, *, exports="from demo.engine import parse\n", owner="TestCase", extra=""):
    package = tmp_path / "src/demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(exports, encoding="utf-8")
    (package / "engine.py").write_text(
        "def parse(value): return value.strip()\ndef setup(): return None\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_table.py").write_text(
        "import unittest\nfrom unittest import TestCase\nimport demo\nfrom demo.engine import setup\n"
        f"class TestTable({owner}):\n{extra}    def test_table(self):\n{test_body}", encoding="utf-8")
    return tmp_path


def analyze(root):
    return _interpret_pytest_result(root, 1,
        "tests/test_table.py:10: in test_table\nE AssertionError: wrong result\n"
        "FAILED tests/test_table.py::TestTable::test_table - AssertionError: wrong result\n", {})


@pytest.mark.parametrize("exports,owner", [
    ("from demo.engine import parse\n", "TestCase"),
    ("from .engine import parse\n", "unittest.TestCase"),
    ("from demo.engine import parse as normalize\n", "TestCase"),
])
def test_table_binding_resolves_exports_and_ignores_setup_and_message(tmp_path, exports, owner):
    name = "normalize" if "as normalize" in exports else "parse"
    root = project(tmp_path,
        "        setup()\n        for given, expected in [(' a ', 'b')]:\n"
        f"            actual = demo.{name}(given)\n"
        "            self.assertEqual(expected, actual, setup())\n", exports=exports, owner=owner)
    result = analyze(root)
    assert result["production_targets"] == ["src/demo/engine.py:parse"]
    assert result["target_binding"] == "unique_assertion_causal_call"


def test_observer_wrapper_stays_opaque(tmp_path):
    root = project(tmp_path,
        "        value = demo.parse('x')\n        actual = self.render(value)\n"
        "        self.assertEqual(actual, 'y')\n",
        extra="    def render(self, value): return str(value)\n")
    assert analyze(root)["production_targets"] == []


@pytest.mark.parametrize("extra,body", [
    ("    def assertEqual(self, a, b): raise AssertionError('unrelated')\n", ""),
    ("", "        self.assertEqual = lambda *args: None\n"),
    ("", "        self = something_else\n"),
    ("", "        self = demo.parse('receiver')\n"),
])
def test_redefined_assertions_do_not_authorize_argument_producers(tmp_path, extra, body):
    root = project(tmp_path, body + "        value = demo.parse('x')\n        self.assertEqual(value, 'y')\n", extra=extra)
    assert analyze(root)["production_targets"] == []


@pytest.mark.parametrize("exports", [
    "from missing.engine import parse\n",
    "from tests.helper import parse\n",
    "from demo.engine import parse\nparse = lambda value: value\n",
    "from demo.engine import parse as other\n",
    "from demo import parse\n",
])
def test_unresolved_or_rebound_exports_stay_unbound(tmp_path, exports):
    root = project(tmp_path, "        self.assertEqual(demo.parse('x'), 'y')\n", exports=exports)
    (root / "tests/helper.py").write_text("def parse(value): return value\n", encoding="utf-8")
    assert analyze(root)["production_targets"] == []


def test_two_asserted_production_functions_remain_ambiguous(tmp_path):
    root = project(tmp_path, "        self.assertEqual(demo.parse('x'), setup())\n")
    result = analyze(root)
    assert result["production_targets"] == []
    assert len(result["causal_analysis"]["candidate_targets"]) == 2
