import sys
import types
from pathlib import Path

from runtime.executable_acceptance_loading import _StubModule, _install_profile_module, _remove_new_modules


def test_dependency_stub_module_has_inspectable_origin() -> None:
    module = _StubModule("optional_dependency")

    assert module.__file__ == "<dependency-stub:optional_dependency>"
    assert module.__spec__ is not None
    assert module.__spec__.submodule_search_locations == []


def test_generated_profile_can_supply_a_real_string_enum(monkeypatch) -> None:
    policy = {
        "generated_module_profiles": {
            "acceptance_dependency.core.enums": {
                "attrs": {"StrEnum": {"__fixture__": "str_enum_class"}}
            }
        }
    }

    created = _install_profile_module("acceptance_dependency.core.enums", policy)
    try:
        module = sys.modules["acceptance_dependency.core.enums"]

        class Value(module.StrEnum):
            ITEM = "item"

        assert Value.ITEM == "item"
        assert module.__file__ == "<dependency-profile:acceptance_dependency.core.enums>"
        assert sys.modules["acceptance_dependency"].__spec__.submodule_search_locations == []
    finally:
        for name in reversed(created):
            monkeypatch.delitem(sys.modules, name, raising=False)


def test_failed_import_cleanup_removes_only_project_owned_modules(monkeypatch, tmp_path: Path) -> None:
    parent = types.ModuleType("acceptance_existing_dependency")
    child = types.ModuleType("acceptance_existing_dependency.lazy_child")
    project_module = types.ModuleType("acceptance_new_project.module")
    child.__file__ = str(tmp_path.parent / "installed" / "lazy_child.py")
    project_module.__file__ = str(tmp_path / "project" / "module.py")
    monkeypatch.setitem(sys.modules, parent.__name__, parent)
    before = set(sys.modules)
    monkeypatch.setitem(sys.modules, child.__name__, child)
    monkeypatch.setitem(sys.modules, project_module.__name__, project_module)

    _remove_new_modules(before, tmp_path)

    assert sys.modules[child.__name__] is child
    assert project_module.__name__ not in sys.modules
