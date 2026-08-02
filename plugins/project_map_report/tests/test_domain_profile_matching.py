from __future__ import annotations

from plugins.project_map_report.src.domain_profile import infer_domain_profile


def test_domain_profile_uses_weighted_kb_project_name_and_text_markers():
    profile = infer_domain_profile(
        {"root": "F:/tmp/requests", "frameworks": [], "entrypoints": ["src/requests/__init__.py"], "routes": 0},
        {"files": [{"path": "README.md", "text": "Requests HTTP library with sessions, adapters, redirects, auth and response handling."}]},
        {
            "files": [
                {
                    "path": "src/requests/sessions.py",
                    "functions": [{"name": "request", "calls": ["send", "prepare_request"]}],
                }
            ],
            "imports": ["urllib3"],
        },
        [],
        {"urllib3"},
    )

    assert profile["kind"] == "http_client_library"
    assert profile["confidence"] >= 0.55
    assert profile["evidence"]


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
