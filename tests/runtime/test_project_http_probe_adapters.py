from pathlib import Path

from runtime.project_http_probe import open_http_probe


def test_http_probe_prefers_method_handler_over_generic_request(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "class FakeResponse:\n"
        "    status_code = 200\n"
        "    content = b'{\"path\":\"/ok\"}'\n"
        "    def json(self):\n"
        "        return {'path': self.path}\n"
        "class FakeClient:\n"
        "    def request(self, method, path):\n"
        "        raise RuntimeError('wrong adapter')\n"
        "    def get(self, path):\n"
        "        response = FakeResponse()\n"
        "        response.path = path\n"
        "        return response\n"
        "class FakeApp:\n"
        "    @property\n"
        "    def test_client(self):\n"
        "        return FakeClient()\n"
        "app = FakeApp()\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/ok", "source": "app.py:index"})

    assert result["status"] == "ok"
    assert result["response"]["sample"] == {"path": "/ok"}


def test_http_probe_supports_async_asgi_client(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "class FakeResponse:\n"
        "    status_code = 200\n"
        "    content = b'{\"path\":\"/asgi\"}'\n"
        "    def json(self):\n"
        "        return {'path': self.path}\n"
        "class FakeASGIClient:\n"
        "    async def request(self, method, path):\n"
        "        response = FakeResponse()\n"
        "        response.path = path\n"
        "        return object(), response\n"
        "class FakeApp:\n"
        "    asgi_client = FakeASGIClient()\n"
        "app = FakeApp()\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/asgi", "source": "app.py:index"})

    assert result["status"] == "ok"
    assert result["response"]["sample"] == {"path": "/asgi"}


def test_http_probe_does_not_follow_fastapi_redirects(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "from fastapi.responses import RedirectResponse\n"
        "app = FastAPI()\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return RedirectResponse('/en', status_code=302)\n",
        encoding="utf-8",
    )

    result = open_http_probe(source, {"method": "GET", "path": "/", "source": "app.py:index"})

    assert result["status"] == "ok"
    assert result["response"]["status_code"] == 302
