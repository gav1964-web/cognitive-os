from __future__ import annotations

from pathlib import Path

import pytest

from runtime.stage2_template_routes import (
    Stage2TemplateRoutesError,
    known_stage2_templates,
    load_stage2_template_routes,
    looks_like_format_continuation,
    requested_output_formats,
    select_stage2_case,
)


ROOT = Path(__file__).resolve().parents[2]


def test_stage2_template_routes_select_cases_from_config():
    routes = load_stage2_template_routes(str(ROOT / "config" / "stage2_template_routes.json"))

    assert "csv_sort_cli" in known_stage2_templates(routes=routes)
    assert select_stage2_case("Напиши FastAPI CRUD для ключей", routes=routes) == "fastapi_kv_store"
    assert select_stage2_case("Напиши CLI сортировку CSV", routes=routes) == "csv_sort_cli"
    assert select_stage2_case("напиши конвертер .md в .rtf", routes=routes) == "generic_file_converter_cli"
    assert select_stage2_case("CLI перечислит содержимое картинки", routes=routes) == "image_contents_cli"


def test_stage2_template_routes_handle_format_continuation_from_config():
    routes = load_stage2_template_routes(str(ROOT / "config" / "stage2_template_routes.json"))

    assert looks_like_format_continuation("добавь вывод в .html и .rtf", routes=routes) is True
    assert requested_output_formats("добавь вывод в .html и .rtf", routes=routes) == [".html", ".rtf"]


def test_stage2_template_routes_reject_unknown_case(tmp_path: Path):
    path = tmp_path / "routes.json"
    path.write_text(
        """{
  "schema_version": "stage2_template_routes.v1",
  "status": "active",
  "known_templates": ["csv_sort_cli"],
  "routes": [{"case": "missing", "all": ["csv"]}],
  "continuation": {}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(Stage2TemplateRoutesError, match="known template"):
        load_stage2_template_routes(str(path))
