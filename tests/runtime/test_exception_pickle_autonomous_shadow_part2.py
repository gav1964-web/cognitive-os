from __future__ import annotations

from tests.runtime.exception_pickle_autonomous_shadow_helpers import *

def test_source_aware_sample_uses_nested_named_object_for_attribute_chain(
    tmp_path: Path,
):
    source = tmp_path / "errors.py"
    source.write_text(
        "class OAuth2Error(Exception):\n"
        "    error = 'invalid_request'\n"
        "    description = ''\n"
        "    def __init__(self, request):\n"
        "        self.request = request\n"
        "        if request.settings.ERROR_URI:\n"
        "            self.error_uri = request.settings.ERROR_URI\n"
        "        super().__init__(f'({self.error}) {self.description}')\n",
        encoding="utf-8",
    )

    sample = _sample_constructor_value_for_source_file(
        "request",
        source_file=source,
        class_name="OAuth2Error",
        object_contracts={},
    )

    assert sample == {
        "__sample__": "named_object",
        "name": "sample-request",
        "settings": {
            "__sample__": "named_object",
            "ERROR_URI": "https://example.invalid/errors/",
            "name": "sample-request-settings",
        },
    }


def test_target_import_stubs_include_relative_modules_and_parent_packages(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "from .base import ExternalBaseError\n"
        "from ..utils import format_error\n",
        encoding="utf-8",
    )

    modules = _target_import_stub_modules(source, module_name="pkg.sub.errors")

    assert "pkg" in modules
    assert "pkg.sub" in modules
    assert "pkg.sub.base" in modules
    assert "pkg.sub.base.ExternalBaseError" in modules
    assert "pkg.utils" in modules
    assert "pkg.utils.format_error" in modules


def test_target_import_stubs_do_not_shadow_standard_library_modules(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n"
        "from .base import ExternalBaseError\n",
        encoding="utf-8",
    )

    modules = _target_import_stub_modules(source, module_name="pkg.errors")

    assert "dataclasses" not in modules
    assert "pathlib" not in modules
    assert "pkg.base" in modules
