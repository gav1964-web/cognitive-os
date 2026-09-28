from __future__ import annotations

from plugins.project_map_report.src.domain_profile import infer_domain_profile
from plugins.project_map_report.src.runtime_readiness import minimal_extraction_plan


def test_dataframe_pipeline_root_purpose_reaches_recognition_confidence():
    profile = infer_domain_profile(
        {"root": "F:/tmp/export_relay", "frameworks": [], "entrypoints": [], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "Typed tabular data pipeline for dataframe and CSV result export.",
                },
                {
                    "path": "writer.py",
                    "text": "def write_json(path, value): pass",
                },
            ]
        },
        {"files": [{"path": "writer.py", "functions": [{"name": "write_json", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "dataframe_pipeline"
    assert profile["confidence"] >= 0.7
    assert any(item.startswith("matched root purpose markers:") for item in profile["evidence"])


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


def test_domain_profile_does_not_treat_quantization_variable_as_qt_gui():
    profile = infer_domain_profile(
        {"root": "F:/tmp/whichllm", "frameworks": [], "entrypoints": ["whichllm/plan.py"], "routes": 0},
        {"files": [{"path": "whichllm/plan.py", "text": "Language model selection: for qt in quant_levels, select_model(qt)."}]},
        {"files": [{"path": "whichllm/plan.py", "functions": [{"name": "select_model", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "llm_application_runtime"


def test_domain_profile_does_not_treat_gui_example_as_core_desktop_app():
    profile = infer_domain_profile(
        {
            "root": "F:/tmp/lark",
            "frameworks": [],
            "entrypoints": ["lark/__init__.py"],
            "routes": 0,
        },
        {
            "files": [
                {"path": "README.md", "text": "Lark is a parsing toolkit for Python."},
                {
                    "path": "examples/advanced/editor.py",
                    "text": "from PyQt5.QtWidgets import QApplication\nwidget = QApplication([])",
                },
            ]
        },
        {
            "files": [
                {"path": "lark/parser.py", "functions": [{"name": "parse", "calls": []}]},
                {
                    "path": "examples/advanced/editor.py",
                    "functions": [{"name": "main", "calls": ["QApplication"]}],
                },
            ],
            "imports": ["PyQt5"],
        },
        [],
        {"PyQt5"},
    )

    assert profile["kind"] != "desktop_gui_ide"


def test_domain_profile_does_not_treat_library_docs_as_site_generator():
    profile = infer_domain_profile(
        {"root": "F:/tmp/cachelib", "frameworks": [], "entrypoints": ["cachelib/__init__.py"], "routes": 0},
        {"files": [{"path": "docs/conf.py", "text": "Sphinx documentation for a cache library."}]},
        {"files": [{"path": "cachelib/base.py", "functions": [{"name": "get", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] != "docs_site_generator"


def test_domain_profile_recognizes_pdoc_as_documentation_generator():
    profile = infer_domain_profile(
        {"root": "F:/tmp/mitmproxy__pdoc", "frameworks": [], "entrypoints": ["pdoc/__init__.py"], "routes": 0},
        {"files": [{"path": "README.md", "text": "pdoc renders Python API documentation."}]},
        {"files": [{"path": "pdoc/render.py", "functions": [{"name": "render", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "docs_site_generator"
    assert profile["confidence"] >= 0.7
    assert any("project name" in row for row in profile["evidence"])


def test_domain_profile_recognizes_unknown_docs_generator_from_root_purpose():
    profile = infer_domain_profile(
        {"root": "F:/tmp/fresh_owner__docforge", "frameworks": [], "entrypoints": ["docforge/main.py"], "routes": 0},
        {
            "files": [
                {"path": "README.md", "text": "DocForge is an API documentation generator for mixed-language source trees."},
                {"path": "requirements.txt", "text": "rich\nconfigparser"},
            ]
        },
        {
            "files": [
                {"path": "docforge/render.py", "functions": [{"name": "render_docs", "calls": ["load_config"]}]}
            ],
            "imports": ["rich", "configparser"],
        },
        [],
        {"rich", "configparser"},
    )

    assert profile["kind"] == "docs_site_generator"
    assert profile["confidence"] >= 0.7
    assert any("root purpose" in row for row in profile["evidence"])


def test_domain_profile_does_not_treat_incidental_rich_dependency_as_terminal_library():
    profile = infer_domain_profile(
        {
            "root": "F:/tmp/gh-action-pypi-publish",
            "frameworks": [],
            "entrypoints": ["oidc-exchange.py", "attestations.py"],
            "routes": 0,
        },
        {
            "files": [
                {"path": "README.md", "text": "GitHub Action to publish distributions to PyPI with OIDC attestations."},
                {"path": "requirements.txt", "text": "rich"},
            ]
        },
        {
            "files": [
                {"path": "attestations.py", "functions": [{"name": "compose_attestation_mapping", "calls": []}]},
                {"path": "oidc-exchange.py", "functions": [{"name": "render_claims", "calls": []}]},
            ]
        },
        [],
        {"rich"},
    )

    assert profile["kind"] == "package_publish_action"


def test_domain_profile_requires_codegen_source_anchor_for_render_helpers():
    profile = infer_domain_profile(
        {"root": "F:/tmp/render_helpers", "frameworks": [], "entrypoints": ["helpers.py"], "routes": 0},
        {"files": [{"path": "helpers.py", "text": "def render_name(value): return value"}]},
        {"files": [{"path": "helpers.py", "functions": [{"name": "render_name", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] != "code_generation_toolkit"


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
