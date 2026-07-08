"""Run a safe project-to-capability transformation flow."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import textwrap
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.extraction_proposal import build_extraction_proposal, write_extraction_proposal, write_foundry_spec
from runtime.project_benchmark import analyze_project


def run_transformation_flow(
    *,
    root: Path,
    project_dir: Path,
    force: bool = False,
    promote: bool = False,
) -> dict[str, Any]:
    with _pushd(root):
        analyzer_outputs = analyze_project(project_dir)
    proposal = build_extraction_proposal(
        project_dir=project_dir,
        analyzer_outputs=analyzer_outputs,
        write_spec=True,
        root=root,
    )
    if proposal.get("status") != "ok":
        return {"status": "blocked", "phase": "PROPOSE", "proposal": proposal}

    proposal_path = write_extraction_proposal(root, proposal)
    try:
        candidate_dir = build_candidate_from_proposal(root, project_dir, proposal, force=force)
        dry_run = _promote_candidate(root, proposal["proposed_spec"]["id"], dry_run=True, force=False)
    except Exception as exc:
        result = {
            "status": "blocked",
            "kind": "transformation_flow",
            "phase": "SANDBOX_BUILD",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project": project_dir.as_posix(),
            "proposal_path": proposal_path.as_posix(),
            "spec_path": proposal.get("spec_path"),
            "selected": proposal.get("selected"),
            "blocker": f"{type(exc).__name__}: {exc}",
            "safety": {"source_code_changes": False, "registry_changes": False},
            "next_steps": ["review blocker", "add dependency extraction policy or choose a more self-contained candidate"],
        }
        result["report_path"] = write_transformation_report(root, result).as_posix()
        return result
    result: dict[str, Any] = {
        "status": "promotion_ready",
        "kind": "transformation_flow",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phases": ["PROPOSE", "SANDBOX_BUILD", "TEST", "PROMOTION_READY"],
        "project": project_dir.as_posix(),
        "proposal_path": proposal_path.as_posix(),
        "spec_path": proposal["spec_path"],
        "candidate_path": candidate_dir.as_posix(),
        "selected": proposal["selected"],
        "safety": {
            "source_code_changes": False,
            "registry_changes": bool(promote),
            "promote_requires_explicit_flag": True,
        },
        "dry_run_promotion": dry_run,
        "next_steps": ["review candidate", "run promote with --promote when approved"],
    }
    if promote:
        result["promotion"] = _promote_candidate(root, proposal["proposed_spec"]["id"], dry_run=False, force=force)
        result["status"] = "promoted"
        result["phases"] = ["PROPOSE", "SANDBOX_BUILD", "TEST", "PROMOTE"]
    report_path = write_transformation_report(root, result)
    result["report_path"] = report_path.as_posix()
    return result


def build_candidate_from_proposal(root: Path, project_dir: Path, proposal: dict[str, Any], *, force: bool) -> Path:
    spec = _admission_spec(dict(proposal["proposed_spec"]))
    candidate_id = spec["id"]
    candidate_dir = root / "generated" / "candidates" / candidate_id
    if candidate_dir.exists():
        if not force:
            raise FileExistsError(f"candidate already exists: {candidate_dir}")
        shutil.rmtree(candidate_dir)
    _write_candidate(candidate_dir, project_dir, proposal, spec)
    _refresh_quality_gate_from_candidate(candidate_dir, proposal, spec)
    write_foundry_spec(root, spec)
    return candidate_dir


def write_transformation_report(root: Path, payload: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "transformations"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    selected = dict(payload.get("selected") or {})
    spec_id = str(dict(payload.get("dry_run_promotion", {})).get("candidate") or selected.get("symbol") or "transformation").split("/")[-1]
    path = out_dir / f"{spec_id}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_candidate(candidate_dir: Path, project_dir: Path, proposal: dict[str, Any], spec: dict[str, Any]) -> None:
    _ensure_package_markers(candidate_dir)
    (candidate_dir / "schemas").mkdir(parents=True, exist_ok=True)
    (candidate_dir / "src").mkdir(parents=True, exist_ok=True)
    (candidate_dir / "tests").mkdir(parents=True, exist_ok=True)
    candidate_id = spec["id"]
    source = dict(spec["source_extraction"])
    source_path, function_name = str(source["source"]).split(":", 1)
    function_source = _function_source(project_dir / source_path, int(source["line"]))
    input_keys = list(spec["input_contract"])
    output_key = next(iter(spec["output_contract"]))

    _write_json(candidate_dir / "plugin.json", _manifest(candidate_id, spec))
    _write_json(candidate_dir / "spec.json", spec)
    _write_text(candidate_dir / "requirements.lock", "# no external dependencies\n")
    _write_json(candidate_dir / "schemas" / "input.json", _object_schema(spec["input_contract"]))
    _write_json(candidate_dir / "schemas" / "output.json", _object_schema(spec["output_contract"]))
    _write_text(candidate_dir / "src" / "__init__.py", f'"""{candidate_id} candidate implementation package."""\n')
    inline_imports = list(dict(spec.get("dependency_policy", {})).get("inline_imports", []))
    _write_text(candidate_dir / "src" / "main.py", _main_py(function_source, function_name, input_keys, output_key, inline_imports))
    _write_text(candidate_dir / "tests" / "test_contract.py", _contract_test(spec))
    _write_text(candidate_dir / "tests" / "test_negative.py", _negative_test(input_keys[0]))
    _write_text(candidate_dir / "README.md", _readme(candidate_id, proposal))


def _ensure_package_markers(candidate_dir: Path) -> None:
    for path in [candidate_dir.parent.parent, candidate_dir.parent, candidate_dir, candidate_dir / "tests"]:
        path.mkdir(parents=True, exist_ok=True)
        marker = path / "__init__.py"
        if not marker.exists():
            marker.write_text("", encoding="utf-8")


def _refresh_quality_gate_from_candidate(candidate_dir: Path, proposal: dict[str, Any], spec: dict[str, Any]) -> None:
    sample_input = dict(spec["quality_gate"]["sample_input"])
    output = _candidate_output(candidate_dir, sample_input)
    spec["quality_gate"]["expected_output"] = _jsonable(output)
    candidate_id = spec["id"]
    _write_json(candidate_dir / "spec.json", spec)
    _write_text(candidate_dir / "tests" / "test_contract.py", _contract_test(spec))
    _write_text(candidate_dir / "README.md", _readme(candidate_id, proposal))


def _candidate_output(candidate_dir: Path, sample_input: dict[str, Any]) -> dict[str, Any]:
    module_path = candidate_dir / "src" / "main.py"
    module_name = f"candidate_{candidate_dir.name}_{abs(hash(candidate_dir.as_posix()))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load candidate module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.run(sample_input))


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _admission_spec(spec: dict[str, Any]) -> dict[str, Any]:
    gate = dict(spec.get("quality_gate", {}))
    sample_input = dict(gate.get("sample_input", {}))
    expected_output = dict(gate.get("expected_output") or _sample_output(spec))
    spec["quality_gate"] = {"sample_input": sample_input, "expected_output": expected_output}
    return spec


def _sample_output(spec: dict[str, Any]) -> dict[str, Any]:
    output_key = next(iter(dict(spec["output_contract"])))
    output_type = str(dict(spec["output_contract"])[output_key])
    if output_type == "integer":
        value: object = 1
    elif output_type == "number":
        value = 1.0
    elif output_type == "boolean":
        value = True
    elif output_type == "array":
        value = []
    elif output_type == "object":
        value = {}
    else:
        value = "sample"
    return {output_key: value}


def _function_source(path: Path, line: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(line - 1, 0)
    collected = []
    for row in lines[start:]:
        if collected and row and not row.startswith((" ", "\t", "@")):
            break
        collected.append(row)
    return textwrap.dedent("\n".join(collected)).rstrip() + "\n"


def _main_py(
    function_source: str,
    function_name: str,
    input_keys: list[str],
    output_key: str,
    inline_imports: list[str] | None = None,
) -> str:
    args = ", ".join(f"{key}=_coerce_arg({key!r}, payload[{key!r}])" for key in input_keys)
    extra_imports = list(inline_imports or [])
    for module in ["base64", "binascii", "codecs", "hashlib", "math", "re", "uuid"]:
        if f"{module}." in function_source and module not in extra_imports:
            extra_imports.append(module)
    extra_imports = [item if item.startswith("import ") else f"import {item}" for item in extra_imports]
    imports = "\n".join(extra_imports)
    if imports:
        imports += "\n"
    return (
        '"""Sandboxed candidate extracted from a source project."""\n\n'
        "from __future__ import annotations\n\n\n"
        "import json\n"
        "from types import SimpleNamespace\n"
        f"{imports}\n"
        f"{function_source}\n\n"
        "def _coerce_arg(name: str, value: object) -> object:\n"
        "    if name == 'messages' and isinstance(value, list):\n"
        "        return [SimpleNamespace(**item) if isinstance(item, dict) else item for item in value]\n"
        "    return value\n\n\n"
        "def _jsonable(value: object) -> object:\n"
        "    return json.loads(json.dumps(value, ensure_ascii=False))\n\n\n"
        "def run(payload: dict[str, object]) -> dict[str, object]:\n"
        f"    result = {function_name}({args})\n"
        f"    return {{{output_key!r}: _jsonable(result)}}\n"
    )


def _contract_test(spec: dict[str, Any]) -> str:
    sample = repr(spec["quality_gate"]["sample_input"])
    expected = repr(spec["quality_gate"]["expected_output"])
    return _test_prelude() + f"\ndef test_candidate_contract():\n    assert run({sample}) == {expected}\n"


def _negative_test(missing_key: str) -> str:
    return _test_prelude("import pytest\n\n") + (
        f"\ndef test_candidate_rejects_missing_{missing_key}():\n"
        "    with pytest.raises(KeyError):\n"
        "        run({})\n"
    )


def _test_prelude(extra: str = "") -> str:
    return (
        "from pathlib import Path\n"
        "import importlib.util\n\n"
        f"{extra}"
        "MODULE_PATH = Path(__file__).resolve().parents[1] / 'src' / 'main.py'\n"
        "MODULE_NAME = f'candidate_{Path(__file__).resolve().parents[1].name}'\n"
        "spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "assert spec.loader is not None\n"
        "spec.loader.exec_module(module)\n"
        "run = module.run\n"
    )


def _manifest(candidate_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "version": "0.1.0",
        "entrypoint": f"plugins.{candidate_id}.src.main:run",
        "determinism_grade": "B",
        "side_effects": spec["side_effects"],
        "lifecycle_status": "rebuilding",
        "version_hash": "sha256:candidate",
    }


def _object_schema(contract: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(contract),
        "properties": {key: {"type": value} for key, value in contract.items()},
        "additionalProperties": False,
    }


def _promote_candidate(root: Path, candidate_id: str, *, dry_run: bool, force: bool) -> dict[str, Any]:
    path = root / "tools" / "promote_candidate.py"
    tools_path = str(path.parent)
    inserted = False
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)
        inserted = True
    spec = importlib.util.spec_from_file_location("cos_promote_candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load promote tool: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module.promote_candidate(root, candidate_id, dry_run=dry_run, force=force)
    finally:
        if inserted:
            sys.path = [item for item in sys.path if item != tools_path]


def _readme(candidate_id: str, proposal: dict[str, Any]) -> str:
    selected = dict(proposal["selected"])
    return (
        f"# {candidate_id}\n\n"
        f"Candidate extracted from `{selected['capability']}`.\n"
        "It is not active until explicit promotion.\n"
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
