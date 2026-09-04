"""Deterministic reducers for qualified framework/plugin regressions."""

from __future__ import annotations

import ast
from typing import Any


def framework_contract_patch(
    source: str, *, symbol: str, operation_kind: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    if symbol != str(recipe.get("required_symbol") or ""):
        return None
    if operation_kind == "guard_empty_theme_config":
        patched = _guard_empty_theme_config(source)
    elif operation_kind == "order_extra_hooks_after_wrappers":
        patched = _order_extra_hooks_after_wrappers(source)
    elif operation_kind == "derive_dist_info_from_wheel_contents":
        patched = _derive_dist_info_from_wheel_contents(source)
    else:
        return None
    if patched is None or patched == source:
        return None
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {"source": patched, "operation_kind": operation_kind}


def _guard_empty_theme_config(source: str) -> str | None:
    if "def _load_theme_config(" not in source or "theme_config = yaml.load(" not in source:
        return None
    anchor = "        log.debug(f\"Loaded theme configuration for '{name}' from '{file_path}': {theme_config}\")\n"
    if anchor not in source or "if theme_config is None:" in source:
        return None
    guard = "        if theme_config is None:\n            theme_config = {}\n\n"
    return source.replace(anchor, guard + anchor, 1)


def _order_extra_hooks_after_wrappers(source: str) -> str | None:
    if "def call_extra(" not in source:
        return None
    old = (
        "            while (\n"
        "                i >= 0\n"
        "                and hookimpls[i].tryfirst\n"
        "                and not (hookimpls[i].hookwrapper or hookimpls[i].wrapper)\n"
        "            ):\n"
        "                i -= 1\n"
    )
    new = (
        "            while i >= 0 and (\n"
        "                (hookimpls[i].hookwrapper or hookimpls[i].wrapper)\n"
        "                or hookimpls[i].tryfirst\n"
        "            ):\n"
        "                i -= 1\n"
    )
    return source.replace(old, new, 1) if source.count(old) == 1 else None


def _derive_dist_info_from_wheel_contents(source: str) -> str | None:
    if "def metadata_path(" not in source:
        return None
    old = (
        "        match = parse_wheel_filename(os.path.basename(wheel))\n"
        "        if not match:\n"
        "            msg = 'Invalid wheel'\n"
        "            raise ValueError(msg)\n"
        "        distinfo = f'{match[\"distribution\"]}-{match[\"version\"]}.dist-info'\n"
        "        member_prefix = f'{distinfo}/'\n"
        "        with zipfile.ZipFile(wheel) as w:\n"
        "            w.extractall(\n"
        "                output_directory,\n"
        "                (member for member in w.namelist() if member.startswith(member_prefix)),\n"
        "            )\n"
    )
    new = (
        "        try:\n"
        "            with zipfile.ZipFile(wheel) as w:\n"
        "                names = w.namelist()\n"
        "        except (OSError, zipfile.BadZipFile) as exception:\n"
        "            msg = 'Invalid wheel'\n"
        "            raise ValueError(msg) from exception\n\n"
        "        metadata_names = [\n"
        "            name for name in names\n"
        "            if name.count('/') == 1 and name.endswith('.dist-info/METADATA')\n"
        "        ]\n"
        "        if len(metadata_names) != 1:\n"
        "            msg = 'Invalid wheel'\n"
        "            raise ValueError(msg)\n"
        "        distinfo = metadata_names[0].rsplit('/', 1)[0]\n"
        "        member_prefix = f'{distinfo}/'\n"
        "        with zipfile.ZipFile(wheel) as w:\n"
        "            w.extractall(\n"
        "                output_directory,\n"
        "                (member for member in names if member.startswith(member_prefix)),\n"
        "            )\n"
    )
    return source.replace(old, new, 1) if source.count(old) == 1 else None
