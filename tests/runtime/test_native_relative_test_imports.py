"""Relative imports must retain test ownership and never select a namesake API."""
import hashlib
from pathlib import Path

import pytest

from runtime.project_native_failure_target_binding import _test_assertion_causal_analysis


def write(root: Path, name: str, source: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


@pytest.mark.parametrize("statement,call", [
    ("from .utils import render as md", "md('x')"),
    ("from . import utils", "utils.render('x')"),
    ("from tests.utils import render as md", "md('x')"),
])
def test_relative_helper_preserves_source_without_binding_production(tmp_path, statement, call):
    write(tmp_path, "tests/__init__.py", "")
    helper = write(tmp_path, "tests/utils.py", "from core import convert\ndef render(value):\n    return convert(value)\n")
    write(tmp_path, "core.py", "def convert(value): return value\n")
    # An unrelated absolute module must never capture the relative import.
    write(tmp_path, "utils.py", "def render(value): return 'wrong'\n")
    write(tmp_path, "tests/test_case.py", f"{statement}\ndef test_case(): assert {call} == 'y'\n")
    result = _test_assertion_causal_analysis(tmp_path, ["tests/test_case.py::test_case"])
    assert result["production_targets"] == []
    assert result["excluded_calls"] == [{"call": call.split("(")[0], "reason": "test_support_call"}]
    source, = result["test_support_sources"]
    assert source["path"] == "tests/utils.py"
    assert source["file_sha256"] == hashlib.sha256(helper.read_bytes()).hexdigest()
    assert source["imports"] == "from core import convert"
    assert source["excerpt_complete"] is True
    assert source["authority"] == "diagnostic_only_not_a_production_target"
    helper.write_text(helper.read_text() + "\n# evidence changed\n", encoding="utf-8")
    changed = _test_assertion_causal_analysis(tmp_path, ["tests/test_case.py::test_case"])
    assert changed["test_support_sources"][0]["file_sha256"] != source["file_sha256"]


@pytest.mark.parametrize("prefix", ["", "src/"])
def test_relative_parent_import_can_bind_a_direct_owned_api(tmp_path, prefix):
    for name in ("pkg/__init__.py", "pkg/tests/__init__.py"):
        write(tmp_path, prefix + name, "")
    write(tmp_path, prefix + "pkg/core.py", "def convert(value): return value\n")
    name = prefix + "pkg/tests/test_case.py"
    write(tmp_path, name, "from ..core import convert\ndef test_case(): assert convert('x') == 'y'\n")
    result = _test_assertion_causal_analysis(tmp_path, [name + "::test_case"])
    assert result["production_targets"] == [prefix + "pkg/core.py:convert"]


@pytest.mark.parametrize("statement", ["from ..utils import render", "from ...utils import render"])
def test_relative_import_above_package_never_binds_absolute_namesake(tmp_path, statement):
    write(tmp_path, "tests/__init__.py", "")
    write(tmp_path, "utils.py", "def render(value): return value\n")
    write(tmp_path, "tests/test_case.py", f"{statement}\ndef test_case(): assert render('x') == 'y'\n")
    result = _test_assertion_causal_analysis(tmp_path, ["tests/test_case.py::test_case"])
    assert result["production_targets"] == []
    assert result["test_support_sources"] == []


def test_relative_import_in_non_package_remains_unbound(tmp_path):
    write(tmp_path, "tests/utils.py", "def render(value): return value\n")
    write(tmp_path, "tests/test_case.py", "from .utils import render\ndef test_case(): assert render('x') == 'y'\n")
    result = _test_assertion_causal_analysis(tmp_path, ["tests/test_case.py::test_case"])
    assert result["production_targets"] == []
    assert result["test_support_sources"] == []


def test_helper_excerpt_is_bounded_without_executing_it(tmp_path):
    write(tmp_path, "tests/__init__.py", "")
    write(tmp_path, "tests/utils.py", "raise RuntimeError('must not import')\n"
          "def render(value):\n    " + repr("x" * 6000) + "\n    return value\n")
    write(tmp_path, "tests/test_case.py", "from .utils import render\ndef test_case(): assert render('x') == 'y'\n")
    result = _test_assertion_causal_analysis(tmp_path, ["tests/test_case.py::test_case"])
    source, = result["test_support_sources"]
    assert len(source["excerpt"]) == 5000
    assert source["excerpt_complete"] is False
    assert result["production_targets"] == []
