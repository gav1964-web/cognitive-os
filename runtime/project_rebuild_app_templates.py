"""Application templates for project rebuild trials."""

from __future__ import annotations

from typing import Any


MAP_ROUTES = {"/get_vector_map", "/incident_meta", "/get_incidents", "/branches_atms", "/search"}


def project_kind(spec: dict[str, Any]) -> str:
    routes = {str(row.get("route")) for row in spec.get("routes", [])}
    if MAP_ROUTES.intersection(routes):
        return "map_flask"
    if routes:
        return "api_fastapi"
    return "tooling_cli"


def build_requirements(spec: dict[str, Any]) -> str:
    kind = project_kind(spec)
    if kind == "api_fastapi":
        return "fastapi>=0.110\nuvicorn>=0.27\n"
    if kind == "map_flask":
        return "Flask>=3.0\n"
    return ""


def build_app_py(spec: dict[str, Any]) -> str:
    kind = project_kind(spec)
    if kind == "api_fastapi":
        return _fastapi_app(spec)
    if kind == "map_flask":
        return _map_flask_app()
    return _cli_app(spec)


def build_contract_tests(spec: dict[str, Any]) -> str:
    kind = project_kind(spec)
    if kind == "api_fastapi":
        return _fastapi_tests(spec)
    if kind == "map_flask":
        return _map_tests()
    return _cli_tests()


def _fastapi_app(spec: dict[str, Any]) -> str:
    handlers = []
    blueprints = _blueprints_by_route(spec)
    for row in spec.get("routes", [])[:12]:
        route = str(row.get("route") or "/")
        methods = [str(item).lower() for item in row.get("methods", [])] or ["get"]
        func = _safe_name(str(row.get("function") or "handler"))
        for method in methods:
            sample = blueprints.get((route, method.upper()), {"route": route, "handler": func, "status": "available"})
            handlers.append(
                f"@app.{method}({route!r})\n"
                f"def {func}_{method}():\n"
                f"    return {sample!r}\n"
            )
    return (
        '"""Minimal API rebuild scaffold generated from source routes."""\n\n'
        "from __future__ import annotations\n\n"
        "from fastapi import FastAPI\n\n"
        "app = FastAPI(title='rebuild api')\n\n"
        + "\n".join(handlers)
        + "\n\ndef main() -> None:\n"
        "    import uvicorn\n"
        "    uvicorn.run(app, host='127.0.0.1', port=8000)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def _cli_app(spec: dict[str, Any]) -> str:
    caps = [str(item) for item in spec.get("core_capabilities", [])[:8]]
    return (
        '"""Minimal tooling rebuild scaffold generated from project evidence."""\n\n'
        "from __future__ import annotations\n\n"
        f"CAPABILITIES = {caps!r}\n\n"
        "def describe() -> dict:\n"
        "    return {'status': 'available', 'capabilities': CAPABILITIES}\n\n"
        "def main() -> None:\n"
        "    print(describe())\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def _fastapi_tests(spec: dict[str, Any]) -> str:
    route = str((spec.get("routes") or [{"route": "/"}])[0].get("route") or "/")
    return (
        "from fastapi.testclient import TestClient\n"
        "from app import app\n\n"
        "def test_first_detected_route_is_available():\n"
        "    response = TestClient(app).request('GET', " + repr(route) + ")\n"
        "    assert response.status_code in {200, 405}\n"
    )


def _cli_tests() -> str:
    return (
        "from app import describe\n\n"
        "def test_describe_exposes_capabilities():\n"
        "    result = describe()\n"
        "    assert result['status'] == 'available'\n"
        "    assert isinstance(result['capabilities'], list)\n"
    )


def _map_tests() -> str:
    return (
        "from app import allowed_highways_for_zoom, app, parse_bbox, point_in_bbox\n\n"
        "def test_parse_bbox_validates_order():\n"
        "    assert parse_bbox('1,2,3,4') == (1.0, 2.0, 3.0, 4.0)\n"
        "    assert parse_bbox('3,2,1,4') is None\n\n"
        "def test_point_in_bbox():\n"
        "    assert point_in_bbox(2, 3, (1, 2, 4, 5)) is True\n\n"
        "def test_zoom_policy_returns_set():\n"
        "    assert 'primary' in allowed_highways_for_zoom(8)\n\n"
        "def test_core_api_routes_return_json():\n"
        "    client = app.test_client()\n"
        "    for route in ['/get_vector_map', '/incident_meta', '/get_incidents', '/branches_atms', '/search?q=sample']:\n"
        "        response = client.get(route)\n"
        "        assert response.status_code == 200\n"
        "        assert response.is_json\n\n"
        "def test_import_start_is_controlled_noop():\n"
        "    response = app.test_client().post('/import_indoc/start')\n"
        "    assert response.status_code == 200\n"
        "    assert response.get_json()['accepted'] is True\n"
    )


def _map_flask_app() -> str:
    from .project_rebuild_map_template import MAP_FLASK_APP

    return MAP_FLASK_APP


def _safe_name(value: str) -> str:
    name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
    return name or "handler"


def _blueprints_by_route(spec: dict[str, Any]) -> dict[tuple[str, str], Any]:
    result = {}
    for row in spec.get("behavior_blueprints", []):
        sample = row.get("sample")
        if sample is not None:
            result[(str(row.get("route")), str(row.get("method") or "GET").upper())] = sample
    return result
