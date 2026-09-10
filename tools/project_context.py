"""Build bounded task context and check the monorepo's declared package boundaries."""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from pathlib import Path

MANIFEST = "docs/architecture/subsystems.json"


def inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repository: {value}")
    return path


def load_manifest(root: Path) -> dict:
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "project_context.v1":
        raise ValueError("unsupported project context manifest")
    return manifest


def check_manifest(root: Path, manifest: dict) -> list[str]:
    errors = []
    subsystems = manifest["subsystems"]
    for name, spec in subsystems.items():
        for dependency in spec["dependencies"]:
            if dependency not in subsystems:
                errors.append(f"{name}: unknown dependency {dependency}")
        for relative in [spec["brief"], *spec["entrypoints"], *spec["contracts"], *spec["tests"]]:
            try:
                if not inside(root, relative).exists():
                    errors.append(f"{name}: missing reference {relative}")
            except ValueError as exc:
                errors.append(str(exc))
    for spec in manifest.get("packages", []):
        try:
            directory = inside(root, spec["source"])
            if not directory.is_dir():
                errors.append(f"missing package source: {spec['source']}")
                continue
            for path in sorted(directory.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                resolved = inside(root, path.as_posix())
                if not resolved.is_relative_to(directory):
                    errors.append(f"package source escapes boundary: {path}")
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    imports = []
                    if isinstance(node, ast.Import):
                        imports = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and not node.level:
                        imports = [node.module or ""]
                    elif isinstance(node, ast.Call) and ast.unparse(node.func).endswith(("import_module", "__import__")):
                        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                            imports = [node.args[0].value]
                        else:
                            errors.append(f"{path.relative_to(root)}:{node.lineno}: unreviewed dynamic import")
                    for module in imports:
                        top = module.split(".")[0]
                        allowed = set(spec["allowed_import_roots"]) | sys.stdlib_module_names | {"__future__"}
                        if top not in allowed:
                            errors.append(f"{path.relative_to(root)}:{node.lineno}: undeclared import {module}")
        except (OSError, ValueError, SyntaxError) as exc:
            errors.append(str(exc))
    return errors


def select_subsystems(root: Path, manifest: dict, names: list[str], paths: list[str]) -> list[str]:
    selected = set(names)
    unknown = selected - manifest["subsystems"].keys()
    if unknown:
        raise ValueError(f"unknown subsystems: {', '.join(sorted(unknown))}")
    for value in paths:
        relative = inside(root, value).relative_to(root.resolve()).as_posix()
        matches = {name for name, spec in manifest["subsystems"].items()
                   if any(fnmatch.fnmatchcase(relative, pattern) for pattern in spec["paths"])}
        if not matches:
            raise ValueError(f"no declared subsystem for {relative}; consult PROJECT_MAP.md")
        selected.update(matches)
    return sorted(selected)


def context(root: Path, manifest: dict, selected: list[str]) -> dict:
    return {
        "schema_version": "task_context.v1",
        "read_first": ["AGENTS.md", "PROJECT_MAP.md", "DEVELOPMENT_STATUS.md"],
        "subsystems": {name: manifest["subsystems"][name] for name in selected},
        "search_roots": manifest["search_roots"],
        "note": "Navigation only. Read the selected code and verify claims; no automatic certification or execution.",
    }


def markdown(root: Path, payload: dict) -> str:
    lines = ["# Task context", "", "Read first: " + ", ".join(payload["read_first"]), ""]
    for name, spec in payload["subsystems"].items():
        lines.extend([f"## {name}: {spec['purpose']}", "", f"Dependencies: {', '.join(spec['dependencies']) or 'none'}", ""])
        brief = inside(root, spec["brief"]).read_text(encoding="utf-8")
        if len(brief) > 12000:
            brief = brief[:12000] + f"\n[truncated; read {spec['brief']} for the rest]\n"
        lines.extend([brief, "Entrypoints: " + ", ".join(spec["entrypoints"]),
                      "Contracts: " + ", ".join(spec["contracts"]), "", "Verification:", ""])
        lines.extend(f"- `{command}`" for command in spec["commands"])
        lines.extend(["", "Search paths: " + ", ".join(spec["paths"]), ""])
    return "\n".join([*lines, payload["note"], ""])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--subsystem", action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional output path inside the repository")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        manifest = load_manifest(root)
        if args.check:
            errors = check_manifest(root, manifest)
            print(json.dumps({"status": "failed" if errors else "ok", "errors": errors}, indent=2))
            return int(bool(errors))
        if args.list or not (args.subsystem or args.path):
            print("\n".join(f"{name}: {spec['purpose']}" for name, spec in manifest["subsystems"].items()))
            return 0
        selected = select_subsystems(root, manifest, args.subsystem, args.path)
        payload = context(root, manifest, selected)
        output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else markdown(root, payload)
        if args.output:
            destination = inside(root, args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
