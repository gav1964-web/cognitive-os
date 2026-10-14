from pathlib import Path

from runtime.project_rebuild_app_templates import build_app_py
from runtime.project_rebuild_behavior import _sample_path
from runtime.project_rebuild_ir import build_rebuild_spec_from_ir


def test_rebuild_spec_marks_html_route_response_kind(tmp_path: Path):
    source = tmp_path / "docs"
    source.mkdir()
    (source / "app.py").write_text(
        "from sanic import html\n"
        "@app.get('/')\n"
        "def index(request):\n"
        "    return html('<main>docs</main>')\n",
        encoding="utf-8",
    )
    ir = {
        "schema_version": "system_knowledge_ir.v0",
        "project_identity": {"name": "docs", "frameworks": ["FastAPI"]},
        "public_interfaces": [{"kind": "route", "name": "/", "function": "index", "methods": ["GET"], "source": "app.py:index"}],
    }

    spec = build_rebuild_spec_from_ir(source_dir=source, ir=ir)

    assert spec["routes"][0]["response_kind"] == "html"


def test_rebuild_spec_marks_redirect_route_response_kind(tmp_path: Path):
    source = tmp_path / "docs"
    source.mkdir()
    (source / "app.py").write_text(
        "from sanic import redirect\n"
        "@app.get('/')\n"
        "def index(request):\n"
        "    return redirect('/en')\n",
        encoding="utf-8",
    )
    ir = {
        "schema_version": "system_knowledge_ir.v0",
        "project_identity": {"name": "docs", "frameworks": ["FastAPI"]},
        "public_interfaces": [{"kind": "route", "name": "/", "function": "index", "methods": ["GET"], "source": "app.py:index"}],
    }

    spec = build_rebuild_spec_from_ir(source_dir=source, ir=ir)

    assert spec["routes"][0]["response_kind"] == "redirect"


def test_fastapi_scaffold_uses_html_response_for_html_routes():
    app_py = build_app_py(
        {
            "target_name": "docs_x",
            "routes": [{"route": "/", "function": "index", "methods": ["GET"], "response_kind": "html"}],
        }
    )

    assert "from fastapi.responses import HTMLResponse" in app_py
    assert "return HTMLResponse" in app_py


def test_fastapi_scaffold_uses_redirect_response_for_redirect_routes():
    app_py = build_app_py(
        {
            "target_name": "docs_x",
            "routes": [{"route": "/", "function": "index", "methods": ["GET"], "response_kind": "redirect"}],
        }
    )

    assert "RedirectResponse" in app_py
    assert "status_code=302" in app_py


def test_sanic_style_route_templates_get_executable_probe_paths():
    assert _sample_path("/<language:str>") == "/en"
    assert _sample_path("/<language:str>/<path:path>") == "/en/index.html"


def test_fastapi_scaffold_converts_sanic_route_templates():
    app_py = build_app_py(
        {
            "target_name": "docs_x",
            "routes": [
                {"route": "/<language:str>/<path:path>", "function": "page", "methods": ["GET"], "response_kind": "html"}
            ],
        }
    )

    assert "@app.get('/{language}/{path:path}')" in app_py
