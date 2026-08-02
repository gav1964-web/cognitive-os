from __future__ import annotations

from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from tests.runtime.test_executable_acceptance import _plan


def test_executable_acceptance_stub_supports_method_base_and_item_access(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "parser.py").write_text(
        "from external_missing import Base, settings\n\n"
        "class Parser(Base):\n"
        "    def parse(self, value):\n"
        "        return {'parsed_url': settings['url'] or value}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/parser.py:parse", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dependency_stub_targets"] == {"src/pkg/parser.py:parse": ["external_missing"]}


def test_executable_acceptance_uses_package_metadata_profile(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "cookiecutter"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(
        "from importlib.metadata import version\n\n"
        "PACKAGE_VERSION = version('cookiecutter')\n\n"
        "def cookiecutter(value):\n"
        "    return {'parsed_url': value, 'version': PACKAGE_VERSION}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("cookiecutter/main.py:cookiecutter", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dependency_metadata_profile_targets"] == {"cookiecutter/main.py:cookiecutter": ["cookiecutter"]}


def test_executable_acceptance_uses_parent_safe_generated_module_profile(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "urllib3" / "util"
    package.mkdir(parents=True)
    (project / "src" / "urllib3" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "url.py").write_text(
        "from urllib3._version import __version__\n\n"
        "def parse_url(value):\n"
        "    return {'parsed_url': value, 'version': __version__}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/urllib3/util/url.py:parse_url", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dependency_module_profile_targets"] == {"src/urllib3/util/url.py:parse_url": ["urllib3._version"]}


def test_executable_acceptance_isolated_function_keeps_needed_helpers_and_imports(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "parser.py").write_text(
        "from .missing_runtime import runtime_value\n"
        "from urllib.parse import urlparse\n\n"
        "def normalize(value: str):\n"
        "    parsed = urlparse(value)\n"
        "    return parsed.scheme or 'missing'\n\n"
        "def parse_url(value: str):\n"
        "    return {'parsed_url': normalize(value)}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/parser.py:parse_url", {"value": "https://example.test"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["src/pkg/parser.py:parse_url"]


def test_executable_acceptance_uses_toml_parse_value_defaults(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def parse_value(src, pos, parse_float, nest_lvl):\n"
        "    value = parse_float('1.5') if src.startswith('\"') and pos == 0 and nest_lvl == 0 else 0\n"
        "    return {'parsed_url': value}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("main.py:parse_value", {"src": '"sample"'}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["main.py:parse_value"] == {
        "nest_lvl": 0,
        "parse_float": {"__fixture__": "callable_float"},
        "pos": 0,
    }


def test_executable_acceptance_uses_configparser_and_asgi_defaults(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "def parse_plugin_options(cfg, cfg_dir, *, enable_extensions=None, require_plugins=None):\n"
        "    paths = cfg.get('flake8:local-plugins', 'paths', fallback='').strip()\n"
        "    return {'paths': paths, 'cfg_dir': cfg_dir, 'enable': enable_extensions}\n\n"
        "class WsgiToAsgiInstance:\n"
        "    def __init__(self, app):\n"
        "        raise RuntimeError('constructor needs app')\n"
        "    def build_environ(self, scope, body):\n"
        "        return {'method': scope['method'], 'path': scope['path'], 'input': body.read()}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "module.py:parse_plugin_options",
                        "kind": "positive_contract_case",
                        "given": {},
                        "expect": {"result": "PluginOptions"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "AC-002",
                        "target": "module.py:build_environ",
                        "kind": "positive_contract_case",
                        "given": {},
                        "expect": {"result": "WsgiEnviron"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-003",
                        "acceptance_id": "side_effect_boundary",
                        "target": "module.py:parse_plugin_options",
                        "kind": "side_effect_scope_case",
                        "given": {},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ]
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["module.py:parse_plugin_options"]["cfg"] == {
        "__fixture__": "configparser_flake8_empty"
    }
    assert result["summary"]["argument_defaults"]["module.py:build_environ"]["body"] == {"__fixture__": "bytes_io_empty"}


def test_executable_acceptance_uses_method_instance_attribute_profile(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "class WsgiToAsgiInstance:\n"
        "    def __init__(self, app):\n"
        "        raise RuntimeError('constructor needs app')\n"
        "    def build_environ(self, scope, body):\n"
        "        return {'method': scope['method'], 'headers': self.scope['headers'], 'limit': self.duplicate_header_limit}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:build_environ", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["module.py:build_environ"]["scope"]["query_string"] == {
        "__fixture__": "bytes_empty"
    }


def test_executable_acceptance_uses_dateutil_numeric_token_defaults(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "class parser:\n"
        "    def _to_decimal(self, value):\n"
        "        return int(value)\n"
        "    def _find_hms_idx(self, idx, tokens, info, allow_jump):\n"
        "        return None\n"
        "    def _parse_numeric_token(self, tokens, idx, info, ymd, res, fuzzy):\n"
        "        if idx + 1 >= len(tokens) or info.jump(tokens[idx + 1]):\n"
        "            ymd.append(self._to_decimal(tokens[idx]))\n"
        "            return idx + 1\n"
        "        return idx\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:_parse_numeric_token", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["module.py:_parse_numeric_token"]["ymd"] == {
        "__fixture__": "dateutil_ymd"
    }


def test_executable_acceptance_uses_pytest_source_fixture(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "from __future__ import annotations\n"
        "import ast\n\n"
        "def getstatementrange_ast(lineno: int, source: Source, assertion: bool = False, astnode: ast.AST | None = None):\n"
        "    node = astnode or ast.parse(str(source), 'source', 'exec')\n"
        "    return node, lineno, len(source.lines)\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:getstatementrange_ast", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["module.py:getstatementrange_ast"]["source"] == {
        "__fixture__": "pytest_source_minimal"
    }


def test_executable_acceptance_rejects_none_result_for_result_contract(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "def prevent_import_hook(name, args):\n"
        "    return None\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "module.py:prevent_import_hook",
                        "kind": "positive_contract_case",
                        "given": {"name": "pip", "args": []},
                        "expect": {"result": "PluginHookResult"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "side_effect_boundary",
                        "target": "module.py:prevent_import_hook",
                        "kind": "side_effect_scope_case",
                        "given": {},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ]
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "meta_only"
    assert result["summary"]["skipped_reason_counts"] == {"positive_sample_execution_failed": 1}
