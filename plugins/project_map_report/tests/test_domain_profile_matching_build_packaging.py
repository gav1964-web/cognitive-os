from __future__ import annotations

from plugins.project_map_report.src.domain_profile import infer_domain_profile
from plugins.project_map_report.src.runtime_readiness import minimal_extraction_plan

def test_domain_profile_can_match_routes_min_kb_rule_for_api_service():
    profile = infer_domain_profile(
        {"root": "F:/tmp/demo_api", "frameworks": ["FastAPI"], "entrypoints": ["app.py"], "routes": 2},
        {"files": [{"path": "app.py", "text": "FastAPI service with JSON endpoint responses."}]},
        {"files": [{"path": "app.py", "functions": [{"name": "create_app", "calls": []}]}], "imports": ["fastapi"]},
        [{"route": "/items"}, {"route": "/health"}],
        {"fastapi"},
    )

    assert profile["kind"] == "api_service"
    assert "routes" in " ".join(profile["evidence"])


def test_domain_profile_prefers_plugin_hook_runtime_over_ml_ui_or_archive_noise():
    profile = infer_domain_profile(
        {"root": "F:/tmp/pluggy", "frameworks": [], "entrypoints": ["src/pluggy/__init__.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "src/pluggy/_callers.py",
                    "text": "def _multicall(...): pass\ndef run_old_style_hookwrapper(...): pass\n# hookspec hookimpl component",
                },
                {"path": "README.md", "text": "pluggy manages hookspec and hookimpl plugin dispatch."},
            ]
        },
        {
            "files": [
                {
                    "path": "src/pluggy/_callers.py",
                    "functions": [
                        {"name": "_multicall", "calls": ["run_old_style_hookwrapper"]},
                        {"name": "run_old_style_hookwrapper", "calls": []},
                    ],
                }
            ],
            "imports": [],
        },
        [],
        set(),
    )

    assert profile["kind"] == "plugin_hook_runtime"
    assert profile["knowledge_rule"] == "plugin_hook_runtime"


def test_domain_profile_keeps_poetry_in_packaging_not_backup_archive():
    profile = infer_domain_profile(
        {"root": "F:/tmp/poetry", "frameworks": [], "entrypoints": ["poetry/console/application.py"], "routes": 0},
        {
            "files": [
                {"path": "poetry/console/commands/init.py", "text": "def _init_pyproject(...): pass\npyproject.toml metadata wheel"},
                {"path": "README.md", "text": "Poetry manages Python package metadata, dependencies, pyproject.toml, build backend and wheel artifacts."},
            ]
        },
        {
            "files": [
                {"path": "poetry/console/commands/init.py", "functions": [{"name": "_init_pyproject", "calls": []}]}
            ],
            "imports": [],
        },
        [],
        set(),
    )

    assert profile["kind"] == "packaging_build_backend"


def test_domain_profile_prefers_owned_build_backend_contract_over_incidental_parser_markers():
    profile = infer_domain_profile(
        {
            "root": "F:/tmp/pypa__setuptools",
            "frameworks": [],
            "entrypoints": [],
            "routes": 0,
        },
        {
            "files": [
                {
                    "path": "README.rst",
                    "text": "Build backend with configuration, parser, section and metadata support.",
                }
            ]
        },
        {
            "files": [
                {
                    "path": "setuptools/build_meta.py",
                    "functions": [
                        {"name": "build_wheel", "calls": []},
                        {"name": "build_sdist", "calls": []},
                        {"name": "prepare_metadata_for_build_wheel", "calls": []},
                    ],
                }
            ],
            "imports": [],
        },
        [],
        set(),
    )

    assert profile["kind"] == "packaging_build_backend"
    assert profile["knowledge_rule"] == "owned_packaging_build_backend"
    assert profile["confidence"] == 0.79
    assert "source contract markers" in " ".join(profile["evidence"])


def test_owned_build_backend_rule_rejects_consumer_only_declaration():
    profile = infer_domain_profile(
        {"root": "F:/tmp/config-consumer", "frameworks": [], "entrypoints": [], "routes": 0},
        {
            "files": [
                {"path": "pyproject.toml", "text": "build-backend = 'setuptools.build_meta'"},
                {"path": "README.md", "text": "Configuration parser for INI sections and keys."},
            ]
        },
        {
            "files": [{
                "path": "src/consumer/config.py",
                "functions": [{"name": "parse_config", "calls": ["configparser.ConfigParser"]}],
            }],
            "imports": ["configparser"],
        },
        [],
        {"configparser"},
    )

    assert profile["kind"] == "configuration_file_parser_library"
    assert profile["knowledge_rule"] != "owned_packaging_build_backend"


def test_domain_profile_matches_registered_owned_pytest_plugin():
    profile = infer_domain_profile(
        {"root": "F:/tmp/sample-plugin", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [
            {"path": "setup.cfg", "text": "[options.entry_points]\npytest11 = sample = sample.plugin"},
            {"path": "sample/plugin.py", "text": "import pytest\n@pytest.fixture\ndef sample_fixture(): pass"},
        ]},
        {"files": [{"path": "sample/plugin.py", "functions": [{"name": "sample_fixture", "calls": []}]}], "imports": ["pytest"]},
        [],
        {"pytest"},
    )

    assert profile["kind"] == "pytest_plugin"
    assert profile["knowledge_rule"] == "owned_pytest_plugin"


def test_owned_pytest_plugin_rule_rejects_test_local_fixture():
    profile = infer_domain_profile(
        {"root": "F:/tmp/pytest-consumer", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [
            {"path": "pyproject.toml", "text": "test = ['pytest']"},
            {"path": "tests/conftest.py", "text": "import pytest\n@pytest.fixture\ndef sample_fixture(): pass"},
        ]},
        {"files": [{"path": "tests/conftest.py", "functions": [{"name": "sample_fixture", "calls": []}]}], "imports": ["pytest"]},
        [],
        {"pytest"},
    )

    assert profile.get("knowledge_rule") != "owned_pytest_plugin"


def test_owned_pytest_plugin_reads_late_bounded_config_entrypoint():
    profile = infer_domain_profile(
        {"root": "F:/tmp/late-entrypoint", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [
            {"path": "setup.cfg", "text": "[metadata]\n" + "description = filler\n" * 80 + "[options.entry_points]\npytest11 = sample = sample.plugin"},
            {"path": "sample/plugin.py", "text": "import pytest\n@pytest.fixture\ndef sample_fixture(): pass"},
        ]},
        {"files": [{"path": "sample/plugin.py", "functions": [{"name": "sample_fixture", "calls": []}]}], "imports": ["pytest"]},
        [],
        {"pytest"},
    )

    assert profile["knowledge_rule"] == "owned_pytest_plugin"


def test_owned_pytest_plugin_reads_late_bounded_plugin_decorator():
    profile = infer_domain_profile(
        {"root": "F:/tmp/late-plugin-hook", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [
            {"path": "pyproject.toml", "text": "[project.entry-points.pytest11]\nsample = 'sample.plugin'"},
            {"path": "sample/plugin.py", "text": "VALUE = 1\n" * 120 + "import pytest\n@pytest.fixture\ndef sample_fixture(): pass"},
        ]},
        {"files": [{"path": "sample/plugin.py", "functions": [{"name": "sample_fixture", "calls": []}]}], "imports": ["pytest"]},
        [],
        {"pytest"},
    )

    assert profile["knowledge_rule"] == "owned_pytest_plugin"


def test_owned_pytest_plugin_accepts_registered_package_module():
    profile = infer_domain_profile(
        {"root": "F:/tmp/package-plugin", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [
            {"path": "pyproject.toml", "text": "[project.entry-points.pytest11]\nsample = 'sample'"},
            {"path": "src/sample/__init__.py", "text": "def pytest_addoption(parser): pass"},
        ]},
        {"files": [{"path": "src/sample/__init__.py", "functions": [{"name": "pytest_addoption", "calls": []}]}], "imports": []},
        [],
        set(),
    )

    assert profile["knowledge_rule"] == "owned_pytest_plugin"


def test_domain_profile_matches_compound_archive_project_name_explicitly():
    profile = infer_domain_profile(
        {"root": "F:/tmp/borgbackup__borg", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.rst", "text": "Deduplicating backup with archive restore and chunks."}]},
        {"files": [{"path": "src/borg/archive.py", "functions": [{"name": "rebuild", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "backup_archive_tool"


def test_domain_profile_matches_dotted_proxy_project_name_explicitly():
    profile = infer_domain_profile(
        {"root": "F:/tmp/abhinavsingh__proxy.py", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Command line interface for an HTTP proxy server with TLS interception and traffic flows."}]},
        {"files": [{"path": "proxy/http/handler.py", "functions": [{"name": "handle", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "proxy_security_tool"


def test_domain_profile_matches_compound_wheel_project_name_explicitly():
    profile = infer_domain_profile(
        {"root": "F:/tmp/auditwheel", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.rst", "text": "Audit and repair Python wheel tags and dist-info metadata."}]},
        {"files": [{"path": "src/auditwheel/wheeltools.py", "functions": [{"name": "repair", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "wheel_package_tool"


def test_domain_profile_does_not_confuse_asgi_server_with_cli_framework():
    profile = infer_domain_profile(
        {"root": "F:/tmp/uvicorn", "frameworks": [], "entrypoints": ["uvicorn/main.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "Uvicorn is an ASGI web server with lifespan, server socket and graceful shutdown support.",
                },
                {"path": "uvicorn/main.py", "text": "import click\n\ndef main(): pass\n"},
            ]
        },
        {"files": [{"path": "uvicorn/server.py", "functions": [{"name": "serve", "calls": ["startup", "shutdown"]}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "asgi_wsgi_server_runtime"
    assert "server startup" in profile["purpose_summary"]


