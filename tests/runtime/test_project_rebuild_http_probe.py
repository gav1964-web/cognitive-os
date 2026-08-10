from pathlib import Path
import sys

from runtime.project_rebuild import compare_rebuild
from runtime.project_http_probe import _load_probe_payload, open_http_probe


def test_http_probe_uses_controlled_stubs_for_external_imports(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    app_source = (
        "from external_router import Router\n"
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return {'status': 'ok'}\n"
    )
    (source / "app.py").write_text(app_source, encoding="utf-8")
    (target / "app.py").write_text(app_source.replace("from external_router import Router\n", ""), encoding="utf-8")

    comparison = compare_rebuild(
        source_dir=source,
        output_dir=target,
        spec={"target_name": "target", "routes": [{"route": "/", "methods": ["GET"], "source": "app.py:index"}]},
        analyzer_outputs={"project_map_report": {"summary": {"routes": 1}}},
    )

    source_case = comparison["behavior"]["cases"][0]["source"]
    assert source_case["status"] == "ok"
    assert source_case["dependency_stubs"] == ["external_router"]
    assert comparison["behavior"]["depth"]["source_stubbed"] == 1
    assert comparison["behavior"]["depth"]["source_evidence_score"] == 0.65
    assert comparison["behavior"]["depth"]["source_dependency_stubs"] == {"external_router": 1}


def test_http_probe_uses_static_route_fallback_when_factory_app_has_no_adapter(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "factory.py").write_text(
        "class FakeApp:\n"
        "    def get(self, route):\n"
        "        def decorate(fn):\n"
        "            return fn\n"
        "        return decorate\n"
        "app = FakeApp()\n"
        "def create_app(root):\n"
        "    return app\n"
        "@app.get('/')\n"
        "async def index(request):\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )
    (target / "app.py").write_text(
        "from flask import Flask, jsonify\n"
        "app = Flask(__name__)\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return jsonify({'handler': 'index', 'route': '/', 'status': 'available'})\n",
        encoding="utf-8",
    )

    comparison = compare_rebuild(
        source_dir=source,
        output_dir=target,
        spec={"target_name": "target", "routes": [{"route": "/", "methods": ["GET"], "source": "factory.py:index"}]},
        analyzer_outputs={"project_map_report": {"summary": {"routes": 1}}},
    )

    source_case = comparison["behavior"]["cases"][0]["source"]
    assert source_case["status"] == "ok"
    assert source_case["dependency_stubs"] == ["static_http_route_fallback"]
    assert source_case["fallback_reason"] == "no supported app adapter"
    assert comparison["behavior"]["depth"]["source_stubbed"] == 1
    assert comparison["behavior"]["depth"]["source_evidence_score"] == 0.7
    assert comparison["behavior"]["depth"]["source_dependency_stubs"] == {"static_http_route_fallback": 1}


def test_http_probe_uses_create_app_factory_when_adapter_supported(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    app_source = (
        "from fastapi import FastAPI\n"
        "def create_app(root):\n"
        "    app = FastAPI()\n"
        "    @app.get('/')\n"
        "    def index():\n"
        "        return {'root': root.name, 'status': 'ok'}\n"
        "    return app\n"
    )
    (source / "factory.py").write_text(app_source, encoding="utf-8")
    (target / "factory.py").write_text(app_source, encoding="utf-8")

    comparison = compare_rebuild(
        source_dir=source,
        output_dir=target,
        spec={"target_name": "target", "routes": [{"route": "/", "methods": ["GET"], "source": "factory.py:index"}]},
        analyzer_outputs={"project_map_report": {"summary": {"routes": 1}}},
    )

    source_case = comparison["behavior"]["cases"][0]["source"]
    assert source_case["status"] == "ok"
    assert source_case["dependency_stubs"] == []
    assert source_case["response"]["sample"]["status"] == "ok"


def test_http_probe_supports_property_test_client_with_tuple_response(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "class FakeResponse:\n"
        "    status_code = 200\n"
        "    content = b'{\"status\":\"ok\"}'\n"
        "    def json(self):\n"
        "        return {'status': 'ok'}\n"
        "class FakeClient:\n"
        "    def get(self, path):\n"
        "        return object(), FakeResponse()\n"
        "class FakeApp:\n"
        "    @property\n"
        "    def test_client(self):\n"
        "        return FakeClient()\n"
        "app = FakeApp()\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/", "source": "app.py:index"})

    assert result["status"] == "ok"
    assert result["response"]["status_code"] == 200
    assert result["response"]["sample"] == {"status": "ok"}


def test_http_probe_loads_json_payload_after_noisy_stdout():
    payload = _load_probe_payload("Main INFO: starting\n{\"status\":\"ok\",\"response\":{\"status_code\":200}}\n")

    assert payload["status"] == "ok"
    assert payload["response"]["status_code"] == 200


def test_http_probe_subprocess_installs_windows_grp_stub(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "import grp\n"
        "import pwd\n"
        "class FakeResponse:\n"
        "    status_code = 200\n"
        "    content = b'{\"group\":\"1\",\"user\":\"2\"}'\n"
        "    def json(self):\n"
        "        return {'group': grp.getgrgid(1).gr_name, 'user': pwd.getpwuid(2).pw_name}\n"
        "class FakeClient:\n"
        "    def __init__(self, app):\n"
        "        self.app = app\n"
        "    def get(self, path):\n"
        "        self.app.shared_ctx.reload_queue.put('reload')\n"
        "        return FakeResponse()\n"
        "class SharedContext:\n"
        "    pass\n"
        "class FakeApp:\n"
        "    def __init__(self):\n"
        "        self.shared_ctx = SharedContext()\n"
        "    @property\n"
        "    def test_client(self):\n"
        "        return FakeClient(self)\n"
        "app = FakeApp()\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/", "source": "app.py:index"}, Path(sys.executable))

    if sys.platform == "win32":
        assert result["status"] == "ok"
        assert result["dependency_stubs"] == []
        assert result["platform_stubs"] == ["grp", "pwd"]
        assert result["response"]["sample"] == {"group": "1", "user": "2"}
    else:
        assert result["status"] in {"ok", "error"}


def test_http_probe_subprocess_prepares_sanic_like_lifecycle_context(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "class FakeResponse:\n"
        "    status_code = 200\n"
        "    content = b'{\"serving\":true}'\n"
        "    def json(self):\n"
        "        return {'serving': app.multiplexer.state['serving']}\n"
        "class FakeClient:\n"
        "    def get(self, path):\n"
        "        app.url_for('page', path=__import__('pathlib').Path('html/index.html'))\n"
        "        app.multiplexer.ack()\n"
        "        app.multiplexer.set_serving(True)\n"
        "        app.multiplexer.terminate()\n"
        "        return FakeResponse()\n"
        "class FakeApp:\n"
        "    @property\n"
        "    def test_client(self):\n"
        "        return FakeClient()\n"
        "    def url_for(self, name, **kwargs):\n"
        "        return str(kwargs['path'])\n"
        "app = FakeApp()\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/", "source": "app.py:index"}, Path(sys.executable))

    assert result["status"] == "ok"
    assert result["response"]["sample"] == {"serving": True}


def test_http_probe_subprocess_uses_static_fallback_on_runtime_error(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "class FakeClient:\n"
        "    def get(self, path):\n"
        "        raise RuntimeError('lifecycle edge')\n"
        "class FakeApp:\n"
        "    @property\n"
        "    def test_client(self):\n"
        "        return FakeClient()\n"
        "    def get(self, route):\n"
        "        def decorate(fn):\n"
        "            return fn\n"
        "        return decorate\n"
        "app = FakeApp()\n"
        "@app.get('/')\n"
        "def index(request):\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/", "source": "app.py:index"}, Path(sys.executable))

    assert result["status"] == "ok"
    assert result["dependency_stubs"][-1] == "static_http_route_fallback"
    assert result["fallback_reason"] == "RuntimeError: lifecycle edge"


def test_http_probe_resolves_nested_project_import_roots(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "guide" / "webapp" / "worker").mkdir(parents=True)
    (source / "guide" / "webapp" / "views.py").write_text("TITLE = 'local'\n", encoding="utf-8")
    (source / "guide" / "webapp" / "worker" / "factory.py").write_text(
        "from webapp.views import TITLE\n"
        "class FakeApp:\n"
        "    def get(self, route):\n"
        "        def decorate(fn):\n"
        "            return fn\n"
        "        return decorate\n"
        "app = FakeApp()\n"
        "@app.get('/')\n"
        "def index(request):\n"
        "    return TITLE\n",
        encoding="utf-8",
    )
    (target / "app.py").write_text(
        "from flask import Flask, jsonify\n"
        "app = Flask(__name__)\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return jsonify({'handler': 'index', 'route': '/', 'status': 'available'})\n",
        encoding="utf-8",
    )

    comparison = compare_rebuild(
        source_dir=source,
        output_dir=target,
        spec={"target_name": "target", "routes": [{"route": "/", "methods": ["GET"], "source": "guide/webapp/worker/factory.py:index"}]},
        analyzer_outputs={"project_map_report": {"summary": {"routes": 1}}},
    )

    source_case = comparison["behavior"]["cases"][0]["source"]
    assert source_case["status"] == "ok"
    assert source_case["dependency_stubs"] == ["static_http_route_fallback"]


def test_http_probe_subprocess_resolves_nested_project_import_roots(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide" / "webapp" / "worker").mkdir(parents=True)
    (source / "guide" / "webapp" / "views.py").write_text("TITLE = 'local'\n", encoding="utf-8")
    (source / "guide" / "webapp" / "worker" / "factory.py").write_text(
        "from fastapi import FastAPI\n"
        "from webapp.views import TITLE\n"
        "def create_app(root):\n"
        "    app = FastAPI()\n"
        "    @app.get('/')\n"
        "    def index():\n"
        "        return {'title': TITLE}\n"
        "    return app\n",
        encoding="utf-8",
    )

    result = open_http_probe(
        source,
        {"method": "GET", "path": "/", "route": "/", "source": "guide/webapp/worker/factory.py:index"},
        python_executable=Path(__import__("sys").executable),
    )

    assert result["status"] == "ok"
    assert result["response"]["sample"] == {"title": "local"}


def test_http_probe_uses_static_route_fallback_when_import_side_effect_fails(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "factory.py").write_text(
        "raise TypeError('import side effect')\n"
        "class FakeApp:\n"
        "    def get(self, route):\n"
        "        def decorate(fn):\n"
        "            return fn\n"
        "        return decorate\n"
        "app = FakeApp()\n"
        "@app.get('/')\n"
        "def index(request):\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    (target / "app.py").write_text(
        "from flask import Flask, jsonify\n"
        "app = Flask(__name__)\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return jsonify({'handler': 'index', 'route': '/', 'status': 'available'})\n",
        encoding="utf-8",
    )

    comparison = compare_rebuild(
        source_dir=source,
        output_dir=target,
        spec={"target_name": "target", "routes": [{"route": "/", "methods": ["GET"], "source": "factory.py:index"}]},
        analyzer_outputs={"project_map_report": {"summary": {"routes": 1}}},
    )

    source_case = comparison["behavior"]["cases"][0]["source"]
    assert source_case["status"] == "ok"
    assert source_case["dependency_stubs"] == ["static_http_route_fallback"]
    assert source_case["fallback_reason"] == "TypeError: import side effect"


def test_http_probe_cleans_exception_stubs_between_static_fallbacks(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "models.py").write_text(
        "from external_struct import Struct\n"
        "class MenuItem(Struct, kw_only=False):\n"
        "    label: str\n",
        encoding="utf-8",
    )
    (source / "factory.py").write_text(
        "from pkg.models import MenuItem\n"
        "class FakeApp:\n"
        "    def get(self, route):\n"
        "        def decorate(fn):\n"
        "            return fn\n"
        "        return decorate\n"
        "app = FakeApp()\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    probe = {"method": "GET", "path": "/", "route": "/", "source": "factory.py:index"}

    first = open_http_probe(source, probe)
    second = open_http_probe(source, probe)

    assert first["dependency_stubs"] == ["external_struct", "static_http_route_fallback"]
    assert second["dependency_stubs"] == ["external_struct", "static_http_route_fallback"]
