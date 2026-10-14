from __future__ import annotations

from pathlib import Path

import pytest

from runtime.capability_routes import CapabilityRoutesError, load_capability_routes, match_capability_route


ROOT = Path(__file__).resolve().parents[2]


def test_capability_routes_match_configured_gigachat_change():
    rules = load_capability_routes(str(ROOT / "config" / "capability_routes.json"))

    capabilities = match_capability_route(
        "по проекту x убери возможность автовыбора модели у провайдера GigaChat",
        rules=rules,
    )

    assert capabilities == ["apply_project_change_recipe"]


def test_capability_routes_reject_bad_route(tmp_path: Path):
    path = tmp_path / "routes.json"
    path.write_text(
        """{
  "schema_version": "capability_routes.v1",
  "status": "active",
  "routes": [{"route_id": "bad"}]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(CapabilityRoutesError, match="all_groups"):
        load_capability_routes(str(path))
