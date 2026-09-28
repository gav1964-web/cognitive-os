from pathlib import Path

from runtime.project_module_probe import module_shape_compatible, open_module_import


def test_module_import_probe_handles_generated_version_metadata(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from importlib.metadata import version\n"
        "from ._version import __version__\n"
        "dist_version = version('pkg')\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_handles_generated_public_version_module(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from pkg.version import version as __version__\n"
        "from pkg.version import version_tuple as __version_tuple__\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_handles_private_version_symbol(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from pkg._version import version\n"
        "__version__ = version\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_handles_missing_package_metadata(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from importlib.metadata import metadata\n"
        "__version__ = metadata('pkg')['Version']\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_handles_lowercase_package_metadata_name(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from importlib.metadata import metadata\n"
        "__version__ = metadata('pkg')['version']\n"
        "project_name = metadata('pkg')['name']\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_handles_package_metadata_summary(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from importlib.metadata import metadata\n"
        "summary = metadata('pkg')['Summary']\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert "summary" in result["shape"]["public_names"]


def test_module_import_probe_handles_package_metadata_get_all(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from importlib.metadata import metadata\n"
        "meta = metadata('pkg')\n"
        "homepage = next(row.split(', ')[1] for row in meta.get_all('Project-URL', ()) if row.startswith('Homepage'))\n"
        "author_email = meta['author-email']\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert "homepage" in result["shape"]["public_names"]


def test_module_import_probe_uses_pep440_probe_version(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "import re\n"
        "from importlib.metadata import version\n"
        "__version__ = version('pkg')\n"
        "assert re.fullmatch(r'(0|[1-9]\\d*)(\\.(0|[1-9]\\d*))*', __version__)\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_uses_package_import_semantics(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text("class App:\n    pass\n", encoding="utf-8")
    (source / "pkg" / "app.py").write_text("from . import App\nVALUE = App\n", encoding="utf-8")

    result = open_module_import(source, {"path": "pkg/app.py"})

    assert result["status"] == "ok"
    assert "VALUE" in result["shape"]["public_names"]


def test_module_import_probe_records_kinds_for_all_sampled_public_names(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    exports = [f"name_{index}" for index in range(20)]
    body = "__all__ = " + repr(exports) + "\n" + "\n".join(f"{name} = {index}" for index, name in enumerate(exports))
    (source / "pkg" / "__init__.py").write_text(body, encoding="utf-8")

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert set(result["shape"]["public_names"]) == set(exports)
    assert set(result["shape"]["attr_kinds"]) == set(exports)


def test_module_import_probe_uses_controlled_stubs_for_external_missing_modules(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from external_dep import thing\n"
        "__all__ = ['run']\n"
        "def run():\n"
        "    return thing()\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["external_dep"]
    assert result["shape"]["public_names"] == ["run"]


def test_module_import_probe_pre_stubs_plugin_loader_side_effects(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from stevedore import ExtensionManager\n"
        "plugins = list(ExtensionManager(namespace='pkg.plugins'))\n"
        "__all__ = ['plugins']\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["stevedore"]
    assert result["shape"]["public_names"] == ["plugins"]


def test_module_import_probe_stub_can_be_used_as_pathlike(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from external_dep import value\n"
        "from pathlib import Path\n"
        "ROOT = Path(value)\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["external_dep"]


def test_module_import_probe_retries_after_partial_package_import_failure(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text("from . import sub\nVALUE = sub.VALUE\n", encoding="utf-8")
    (source / "pkg" / "sub.py").write_text("from external_dep import value\nVALUE = value\n", encoding="utf-8")

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["external_dep"]
    assert "VALUE" in result["shape"]["public_names"]


def test_module_import_probe_preserves_version_fallback_after_retry(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "try:\n"
        "    import external_dep\n"
        "except ModuleNotFoundError:\n"
        "    raise\n"
        "from pkg._version import __version__\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["version_present"] is True


def test_module_import_probe_keeps_shape_when_lazy_public_attr_fails(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "__all__ = ['ready', 'lazy']\n"
        "ready = 1\n"
        "def __getattr__(name):\n"
        "    if name == 'lazy':\n"
        "        raise ModuleNotFoundError(\"No module named 'external_dep'\", name='external_dep')\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["shape"]["attr_kinds"]["lazy"] == "unavailable"


def test_module_import_probe_metadata_profile_has_author(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "from importlib.metadata import metadata\n"
        "author = metadata('pkg')['Author']\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert "author" in result["shape"]["public_names"]


def test_module_import_probe_uses_static_shape_for_asserting_package_init(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "context.py").write_text("raise AssertionError()\n", encoding="utf-8")
    (source / "pkg" / "__init__.py").write_text(
        "from . import context\n"
        "__version__ = '1.0.0'\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["static_shape_fallback"]
    assert result["shape"]["public_source"] == "static_ast_fallback"
    assert result["shape"]["version_present"] is True
    assert "context" in result["shape"]["public_names"]


def test_module_import_probe_uses_static_shape_for_package_init_import_side_effect(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "public_name = 'available'\n"
        "raise TypeError(\"'FunctionNamespace' object does not support item assignment\")\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["static_shape_fallback"]
    assert result["shape"]["public_source"] == "static_ast_fallback"
    assert "public_name" in result["shape"]["public_names"]


def test_module_import_probe_preserves_stubs_on_static_shape_fallback(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "import external_native_dep\n"
        "public_name = 'available'\n"
        "raise TypeError(\"'FunctionNamespace' object does not support item assignment\")\n",
        encoding="utf-8",
    )

    result = open_module_import(source, {"path": "pkg/__init__.py"})

    assert result["status"] == "ok"
    assert result["dependency_stubs"] == ["external_native_dep", "static_shape_fallback"]


def test_module_shape_compatible_rejects_missing_all_exports():
    assert (
        module_shape_compatible(
            {"public_source": "__all__", "public_names": ["run"], "attr_kinds": {"run": "function"}},
            {"public_source": "__all__", "public_names": ["run"], "attr_kinds": {"run": "NoneType"}},
        )
        is False
    )
