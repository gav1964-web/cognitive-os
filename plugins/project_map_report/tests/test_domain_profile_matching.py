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


def test_domain_profile_prefers_logging_library_over_incidental_gunicorn_mention():
    profile = infer_domain_profile(
        {"root": "F:/tmp/acme_logging", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "acme/formatters.py", "text": "import logging\nclass EventFormatter(logging.Formatter): pass\n# gunicorn compatible"}]},
        {"files": [{"path": "acme/formatters.py", "functions": [{"name": "formatMessage", "calls": []}]}]},
        [],
        {"logging"},
    )

    assert profile["kind"] == "logging_library"


def test_domain_profile_does_not_treat_navigation_substrings_as_docs_generator():
    profile = infer_domain_profile(
        {"root": "F:/tmp/async_store", "frameworks": [], "entrypoints": ["store/client.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "store/client.py",
                    "text": "async def execute_command(): pass\ndef invalid_response(): pass\nnavigation_state = None\nrewrite = False",
                }
            ]
        },
        {
            "files": [
                {"path": "store/client.py", "functions": [{"name": "execute_command", "calls": ["read_response"]}]}
            ],
            "imports": ["asyncio"],
        },
        [],
        set(),
    )

    assert profile["kind"] != "docs_site_generator"
    assert profile["kind"] != "env_config_library"


def test_domain_profile_does_not_confuse_container_agent_with_multi_agent_runtime():
    profile = infer_domain_profile(
        {"root": "F:/tmp/container_manager", "frameworks": ["FastAPI"], "entrypoints": ["backend/app.py"], "routes": 8},
        {"files": [{"path": "README.md", "text": "Self-hosted app for automating Docker container updates, image pruning, and private registries. Remote hosts use an agent."}]},
        {"files": [{"path": "backend/update.py", "functions": [{"name": "build_update_plan", "calls": []}]}], "imports": ["fastapi"]},
        [],
        {"fastapi"},
    )

    assert profile["kind"] == "container_update_management_service"


def test_domain_profile_requires_semantic_multi_agent_marker():
    profile = infer_domain_profile(
        {"root": "F:/tmp/agents", "frameworks": ["FastAPI"], "entrypoints": ["api.py"], "routes": 3},
        {"files": [{"path": "README.md", "text": "Agent-to-agent service with AgentCard exchange and consensus orchestration."}]},
        {"files": [{"path": "orchestrator.py", "functions": [{"name": "run_consensus", "calls": []}]}], "imports": ["fastapi"]},
        [],
        {"fastapi"},
    )

    assert profile["kind"] == "multi_agent_orchestration_runtime"


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


def test_domain_profile_does_not_confuse_chunked_arrays_with_template_engine():
    profile = infer_domain_profile(
        {"root": "F:/tmp/zarr-python", "frameworks": [], "entrypoints": ["src/zarr/__init__.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "Zarr implements compressed, chunked, N-dimensional arrays for parallel computing.",
                },
                {"path": "src/zarr/core.py", "text": "class Array: pass\n# metadata templates are examples only\n"},
            ]
        },
        {"files": [{"path": "src/zarr/core.py", "functions": [{"name": "open_array", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "scientific_compute_library"


def test_domain_profile_keeps_mako_template_engine_with_wsgi_mentions():
    profile = infer_domain_profile(
        {"root": "F:/tmp/mako", "frameworks": [], "entrypoints": ["mako/__init__.py"], "routes": 0},
        {"files": [{"path": "README.rst", "text": "Mako is a template library written in Python with WSGI examples."}]},
        {"files": [{"path": "mako/template.py", "functions": [{"name": "render", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "template_rendering_engine"


def test_domain_profile_ignores_changelog_template_noise_for_small_libraries():
    profile = infer_domain_profile(
        {"root": "F:/tmp/multidict", "frameworks": [], "entrypoints": ["multidict/__init__.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.rst",
                    "text": "Multidict is dict-like collection where a key might occur more than once.",
                },
                {
                    "path": "CHANGES/.TEMPLATE.rst",
                    "text": "Internal release template mentioning Jinja and Mako rendering examples.",
                },
            ]
        },
        {"files": [{"path": "multidict/__init__.py", "functions": [{"name": "MultiDict", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "multi_value_mapping_library"


def test_domain_profile_ignores_doc_spelling_wordlist_template_noise():
    profile = infer_domain_profile(
        {"root": "F:/tmp/aiosignal", "frameworks": [], "entrypoints": ["aiosignal/__init__.py"], "routes": 0},
        {
            "files": [
                {"path": "README.rst", "text": "A project to manage callbacks in asyncio projects."},
                {"path": "docs/spelling_wordlist.txt", "text": "Jinja\nMako\n"},
            ]
        },
        {"files": [{"path": "aiosignal/__init__.py", "functions": [{"name": "Signal", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "async_callback_signal_library"


def test_domain_profile_ignores_dev_tooling_noise_for_small_libraries():
    profile = infer_domain_profile(
        {"root": "F:/tmp/aiosignal", "frameworks": [], "entrypoints": ["aiosignal/__init__.py"], "routes": 0},
        {
            "files": [
                {"path": "README.rst", "text": "A project to manage callbacks in asyncio projects."},
                {"path": "pyproject.toml", "text": "[tool.ruff]\n[tool.mypy]\n"},
            ]
        },
        {"files": [{"path": "aiosignal/__init__.py", "functions": [{"name": "Signal", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "async_callback_signal_library"


def test_domain_profile_keeps_pyyaml_out_of_http_client_noise():
    profile = infer_domain_profile(
        {"root": "F:/tmp/pyyaml", "frameworks": [], "entrypoints": ["lib/yaml/__init__.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "A full-featured YAML processing framework for Python with safe_load and LibYAML bindings.",
                }
            ]
        },
        {"files": [{"path": "lib/yaml/__init__.py", "functions": [{"name": "safe_load", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "yaml_processing_framework"


def test_domain_profile_recognizes_django_framework_without_routes():
    profile = infer_domain_profile(
        {"root": "F:/tmp/django", "frameworks": [], "entrypoints": ["django/__init__.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.rst",
                    "text": "Django is a high-level Python web framework with django.conf and management/commands.",
                }
            ]
        },
        {"files": [{"path": "django/conf/__init__.py", "functions": [{"name": "configure", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "django_web_framework"


def test_domain_profile_does_not_treat_infra_blueprint_text_as_web_framework():
    profile = infer_domain_profile(
        {"root": "F:/tmp/deployment-toolkit", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Deployment blueprint for infrastructure."}]},
        {"files": []},
        [],
        set(),
    )

    assert profile["kind"] == "generic"


def test_domain_profile_recognizes_repeated_transform_library_callables():
    profile = infer_domain_profile(
        {"root": "F:/tmp/sample_tool", "frameworks": [], "entrypoints": ["mod_0.py"], "routes": 0},
        {"files": []},
        {
            "files": [
                {
                    "path": "mod_0.py",
                    "functions": [
                        {"name": "normalize_name", "calls": []},
                        {"name": "normalize_email", "calls": []},
                        {"name": "validate_value", "calls": []},
                    ],
                }
            ]
        },
        [],
        set(),
    )

    assert profile["kind"] == "python_transform_library"
    assert len(profile["scenario_summary"]) >= 3


def test_domain_profile_recognizes_deep_learning_image_pipeline():
    profile = infer_domain_profile(
        {"root": "F:/tmp/image_lab", "frameworks": [], "entrypoints": ["models.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "Train a convolutional network for image enhancement using a paired image dataset and model checkpoints.",
                }
            ]
        },
        {"files": [{"path": "models.py", "functions": [{"name": "forward", "calls": []}]}]},
        [],
        {"tensorflow"},
    )

    assert profile["kind"] == "deep_learning_image_pipeline"
    assert len(profile["scenario_summary"]) >= 3


def test_domain_profile_recognizes_neural_network_training_pipeline():
    profile = infer_domain_profile(
        {"root": "F:/tmp/neural_lab", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Train a neural network with stochastic gradient descent and backpropagation."}]},
        {"files": [{"path": "network.py", "functions": [{"name": "backprop", "calls": []}]}]},
        [],
        {"numpy"},
    )
    assert profile["kind"] == "neural_network_training_pipeline"
    assert "gradients and updated parameters" in profile["output_summary"]


def test_domain_profile_recognizes_blender_animation_addon():
    profile = infer_domain_profile(
        {"root": "F:/tmp/animtoolbox", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Animation and rigging tools for Blender."}]},
        {
            "files": [
                {
                    "path": "BakeToCtrl.py",
                    "functions": [{"name": "constraint_add", "calls": ["bpy.ops.pose.constraint_add"]}],
                }
            ]
        },
        [],
        {"bpy"},
    )

    assert profile["kind"] == "blender_animation_addon"
    assert len(profile["scenario_summary"]) >= 3
