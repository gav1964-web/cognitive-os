"""Library binding suggestions for generic file conversion recipes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .generic_file_conversion_recipe import ConversionRecipe, build_conversion_recipe


@dataclass(frozen=True)
class LibraryBindingRecipe:
    source_ext: str
    target_ext: str
    candidates: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "LibraryBindingRecipe",
            "status": "candidate",
            "source_ext": self.source_ext,
            "target_ext": self.target_ext,
            "selection_policy": "prefer stdlib fixture adapter for tests; enable real backend only by explicit dependency decision",
            "default_backend": "fixture_adapter",
            "candidates": list(self.candidates),
            "verification_policy": [
                "default tests must pass without optional libraries",
                "real backend requires separate optional smoke",
                "adapter output must satisfy target extension contract",
                "dependency failures must become controlled errors",
            ],
            "authority": {
                "may_install_dependencies": False,
                "may_call_network": False,
                "may_replace_adapter_contract": False,
            },
        }


def build_library_binding_recipe(prompt: str) -> LibraryBindingRecipe | None:
    conversion = build_conversion_recipe(prompt)
    if conversion is None:
        return None
    return build_library_binding_recipe_from_conversion(conversion)


def build_library_binding_recipe_from_conversion(conversion: ConversionRecipe) -> LibraryBindingRecipe:
    pair = (conversion.source_ext, conversion.target_ext)
    candidates = _known_candidates(pair) or _generic_candidates(conversion)
    return LibraryBindingRecipe(
        source_ext=conversion.source_ext,
        target_ext=conversion.target_ext,
        candidates=tuple(candidates),
    )


def library_binding_json(prompt: str) -> str:
    recipe = build_library_binding_recipe(prompt)
    if recipe is None:
        raise ValueError("prompt does not describe a two-format file conversion")
    return json.dumps(recipe.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _known_candidates(pair: tuple[str, str]) -> list[dict[str, Any]]:
    if pair == (".xls", ".png"):
        return [
            {
                "backend_id": "libreoffice_headless_render",
                "libraries": ["LibreOffice/headless"],
                "pipeline": ["open workbook", "export selected sheet/page to PDF or image", "normalize to PNG"],
                "quality": "high_fidelity",
                "risks": ["external binary required", "platform-dependent rendering"],
                "enabled_by_default": False,
            },
            {
                "backend_id": "xlrd_plus_pillow_table_preview",
                "libraries": ["xlrd", "Pillow"],
                "pipeline": ["read cell grid", "render table preview", "write PNG"],
                "quality": "semantic_table_preview",
                "risks": ["not pixel-faithful to Excel layout", "legacy xls parser dependency"],
                "enabled_by_default": False,
            },
        ]
    if pair == (".md", ".rtf"):
        return [
            {
                "backend_id": "stdlib_markdown_subset_to_rtf",
                "libraries": [],
                "pipeline": ["parse safe Markdown subset", "escape RTF text", "write RTF envelope"],
                "quality": "bounded_subset",
                "risks": ["full Markdown extensions are not supported"],
                "enabled_by_default": False,
            },
            {
                "backend_id": "pandoc_adapter",
                "libraries": ["pandoc"],
                "pipeline": ["call pandoc with explicit input/output formats", "capture stderr", "write RTF"],
                "quality": "high_fidelity",
                "risks": ["external binary required"],
                "enabled_by_default": False,
            },
        ]
    if pair == (".txt", ".html"):
        return [
            {
                "backend_id": "stdlib_text_to_html",
                "libraries": [],
                "pipeline": ["read UTF-8 text", "HTML-escape content", "wrap in document"],
                "quality": "safe_plain_text",
                "risks": ["plain text only, no rich formatting"],
                "enabled_by_default": False,
            }
        ]
    if pair in {(".jpg", ".doc"), (".jpeg", ".doc"), (".png", ".doc")}:
        return [
            {
                "backend_id": "stdlib_image_to_doc_html",
                "libraries": [],
                "pipeline": ["read image bytes", "base64-embed image in DOC-compatible HTML", "write .doc file"],
                "quality": "doc_compatible_image_wrapper",
                "risks": ["not native binary Word format", "image content is embedded but not semantically interpreted"],
                "enabled_by_default": False,
            },
            {
                "backend_id": "python_docx_plus_pillow",
                "libraries": ["python-docx", "Pillow"],
                "pipeline": ["validate image", "create Word document", "insert image", "save docx-compatible document"],
                "quality": "native_word_document_when_docx_allowed",
                "risks": ["external dependencies required", ".doc legacy binary format is not produced by python-docx"],
                "enabled_by_default": False,
            },
        ]
    return []


def _generic_candidates(conversion: ConversionRecipe) -> list[dict[str, Any]]:
    return [
        {
            "backend_id": "custom_adapter_required",
            "libraries": [],
            "pipeline": [
                f"read {conversion.source_ext} payload",
                "normalize through project-specific adapter",
                f"write {conversion.target_ext} artifact",
            ],
            "quality": "contract_only_until_backend_selected",
            "risks": ["no known deterministic backend for this format pair"],
            "enabled_by_default": False,
        }
    ]
