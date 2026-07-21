"""Generic recipe extraction for simple file conversion CLI prompts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


_EXT_RE = re.compile(r"(?<![A-Za-z0-9])\.([A-Za-z0-9]{2,8})(?![A-Za-z0-9])")
_EXT_PAIR_RE = re.compile(r"(?<![A-Za-z0-9])\.[A-Za-z0-9]{2,8}\s+(?:в|to|->|=>)\s+\.[A-Za-z0-9]{2,8}(?![A-Za-z0-9])")


@dataclass(frozen=True)
class ConversionRecipe:
    source_ext: str
    target_ext: str
    package: str = "file_converter_cli"

    @property
    def source_format(self) -> str:
        return self.source_ext.lstrip(".")

    @property
    def target_format(self) -> str:
        return self.target_ext.lstrip(".")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "GenericFileConversionRecipe",
            "package": self.package,
            "task_type": "file_conversion_cli",
            "source_ext": self.source_ext,
            "target_ext": self.target_ext,
            "pipeline": [
                "validate input path and extension",
                "read source bytes",
                "pass normalized payload through adapter boundary",
                "write target artifact",
            ],
            "dependency_strategy": {
                "default": "stdlib fixture adapter",
                "production": "optional backend behind converter adapter contract",
                "network_required": False,
            },
            "controlled_failures": [
                "missing input file",
                "unsupported input extension",
                "unsupported output extension",
                "adapter backend unavailable",
            ],
        }


def is_file_conversion_prompt(prompt: str) -> bool:
    lower = prompt.lower()
    has_conversion_verb = any(marker in lower for marker in ("convert", "converter", "конверт", "преобраз", "перевод"))
    has_conversion_pair = _EXT_PAIR_RE.search(lower) is not None
    return (has_conversion_verb or has_conversion_pair) and len(_extensions(prompt)) >= 2


def build_conversion_recipe(prompt: str) -> ConversionRecipe | None:
    extensions = _extensions(prompt)
    if len(extensions) < 2:
        return None
    return ConversionRecipe(source_ext=extensions[0], target_ext=extensions[1])


def recipe_json(prompt: str) -> str:
    recipe = build_conversion_recipe(prompt)
    if recipe is None:
        raise ValueError("prompt does not describe a two-format file conversion")
    return json.dumps(recipe.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _extensions(prompt: str) -> list[str]:
    found: list[str] = []
    for match in _EXT_RE.finditer(prompt):
        ext = f".{match.group(1).lower()}"
        if ext not in found:
            found.append(ext)
    if len(found) > 2 and found[0] == ".py":
        found = found[1:]
    return found
