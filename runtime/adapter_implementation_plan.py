"""Adapter implementation plan for generated generic converters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .generic_file_conversion_recipe import ConversionRecipe, build_conversion_recipe
from .library_binding_recipe import build_library_binding_recipe_from_conversion


@dataclass(frozen=True)
class AdapterImplementationPlan:
    source_ext: str
    target_ext: str
    selected_backend: str
    implementation_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "AdapterImplementationPlan",
            "status": self.implementation_status,
            "source_ext": self.source_ext,
            "target_ext": self.target_ext,
            "selected_backend": self.selected_backend,
            "dependency_changes": [],
            "files_to_change": [
                "src/file_converter_cli/adapters.py",
                "src/file_converter_cli/converter.py",
                "tests/test_adapter_backend.py",
            ],
            "fallback": "fixture_adapter",
            "controlled_errors": [
                "missing input file",
                "unsupported input extension",
                "unsupported output extension",
                "empty input file",
            ],
            "verification": [
                "project-scoped pytest",
                "module CLI smoke",
                "adapter output semantic assertion",
            ],
            "authority": {
                "may_install_dependencies": False,
                "may_call_network": False,
                "may_edit_user_source": False,
            },
        }


def build_adapter_implementation_plan(prompt: str) -> AdapterImplementationPlan | None:
    conversion = build_conversion_recipe(prompt)
    if conversion is None:
        return None
    return build_adapter_implementation_plan_from_conversion(conversion)


def build_adapter_implementation_plan_from_conversion(conversion: ConversionRecipe) -> AdapterImplementationPlan:
    binding = build_library_binding_recipe_from_conversion(conversion)
    stdlib_candidates = [
        str(item.get("backend_id"))
        for item in binding.candidates
        if item.get("libraries") == [] and str(item.get("backend_id")).startswith("stdlib_")
    ]
    if stdlib_candidates:
        return AdapterImplementationPlan(
            source_ext=conversion.source_ext,
            target_ext=conversion.target_ext,
            selected_backend=stdlib_candidates[0],
            implementation_status="implemented",
        )
    return AdapterImplementationPlan(
        source_ext=conversion.source_ext,
        target_ext=conversion.target_ext,
        selected_backend="fixture_adapter",
        implementation_status="fallback_only",
    )


def adapter_implementation_plan_json(prompt: str) -> str:
    plan = build_adapter_implementation_plan(prompt)
    if plan is None:
        raise ValueError("prompt does not describe a two-format file conversion")
    return json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
