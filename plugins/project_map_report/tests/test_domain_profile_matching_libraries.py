from __future__ import annotations

from plugins.project_map_report.src.domain_profile import infer_domain_profile
from plugins.project_map_report.src.runtime_readiness import minimal_extraction_plan

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


def test_domain_profile_prefers_api_client_over_incidental_dataframe_boundaries():
    profile = infer_domain_profile(
        {"root": "F:/tmp/acme-python-sdk", "frameworks": [], "entrypoints": ["acme/__init__.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "The Acme API SDK authenticates clients and manages users. Dataset methods accept pandas DataFrames.",
                },
                {
                    "path": "acme/client.py",
                    "text": "import requests\nfrom pandas import DataFrame\nclass Client:\n    def request(self): pass",
                },
            ]
        },
        {
            "files": [
                {
                    "path": "acme/client.py",
                    "functions": [
                        {"name": "request", "calls": ["requests.get"]},
                        {"name": "login", "calls": []},
                    ],
                }
            ],
            "imports": ["pandas", "requests"],
        },
        [],
        {"pandas", "requests"},
    )

    assert profile["kind"] == "protocol_api_client"
    assert "matched source markers" in " ".join(profile["evidence"])
    assert "external API" in profile["purpose_summary"]


def test_domain_profile_recognizes_rest_client_from_owned_request_flow():
    profile = infer_domain_profile(
        {
            "root": "F:/tmp/allisson__python-simple-rest-client",
            "frameworks": [],
            "entrypoints": ["simple_rest_client/__init__.py"],
            "routes": 0,
        },
        {
            "files": [
                {
                    "path": "README.rst",
                    "text": "A simple REST client for Python with resources and HTTP responses.",
                },
                {
                    "path": "simple_rest_client/request.py",
                    "text": "def make_request(client, request): return client.request(request.method, request.url)",
                },
            ]
        },
        {
            "files": [
                {
                    "path": "simple_rest_client/request.py",
                    "functions": [{"name": "make_request", "calls": ["client.request"]}],
                },
                {
                    "path": "simple_rest_client/api.py",
                    "functions": [{"name": "add_resource", "calls": []}],
                },
            ],
            "imports": ["httpx"],
        },
        [],
        {"httpx"},
    )

    assert profile["kind"] == "protocol_api_client"
    assert profile["knowledge_rule"] == "protocol_api_client"


