"""Native collected-test identity and callable/module name collisions."""
import ast

import pytest

from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.project_native_failure_target_binding import _imported_call_target


@pytest.mark.parametrize('export', ['from .render import render', 'from .render import *'])
def test_exported_callable_precedes_same_named_submodule(tmp_path, export):
    package=tmp_path/'pkg'
    package.mkdir()
    (package/'__init__.py').write_text(export+'\n')
    (package/'render.py').write_text('__all__ = ["render"]\ndef render(value):\n    return value\n')
    result=_imported_call_target(tmp_path,ast.Name(id='render'),{'render':('pkg','render')})
    assert result == 'pkg/render.py:render'


@pytest.mark.parametrize('declaration', ['__all__ = []', '__all__ = unknown()', '__all__ = ["render"]\n__all__.clear()'])
def test_star_import_does_not_invent_hidden_or_dynamic_exports(tmp_path, declaration):
    package=tmp_path/'pkg'
    package.mkdir()
    (package/'__init__.py').write_text('from .render import *\n')
    (package/'render.py').write_text(declaration+'\ndef render(value):\n    return value\n')
    assert _imported_call_target(tmp_path,ast.Name(id='render'),{'render':('pkg','render')}) is None


def test_collected_test_with_nonstandard_filename_is_not_production(tmp_path):
    (tmp_path/'library.py').write_text('def transform(value):\n    return value\n')
    (tmp_path/'checks.py').write_text('from library import transform\ndef test_value():\n    assert transform(2) == 4\n')
    output='E AssertionError: assert 2 == 4\nchecks.py:3: AssertionError\nFAILED checks.py::test_value - AssertionError\n'
    result=_interpret_pytest_result(tmp_path,1,output,{})
    assert result['leaf_production_target'] == 'library.py:transform'
    assert result['target_binding'] == 'unique_assertion_causal_call'
