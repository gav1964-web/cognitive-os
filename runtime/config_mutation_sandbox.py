"""Validate proposed config mutations without applying them."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from .l4_decision_table import load_l4_decision_rules
from .operation_recipe_rules import load_operation_recipe_rules
from .prompt_intake_rules import load_prompt_intake_rules
from .role_directory import load_role_directory
from .runtime_interpreter_policy import load_runtime_interpreter_policy
from .sandbox_programmer_profiles import load_sandbox_programmer_profiles
from .sandbox_release_policy import load_sandbox_release_policy
from .semantic_resolution_rules import load_semantic_resolution_rules
from .stage2_template_routes import load_stage2_template_routes


VALIDATORS: dict[str, Callable[[str], Any]] = {
    "config/l4_decision_rules.json": load_l4_decision_rules,
    "config/operation_recipe_rules.json": load_operation_recipe_rules,
    "config/prompt_intake_rules.json": load_prompt_intake_rules,
    "config/role_directory.json": load_role_directory,
    "config/runtime_interpreter_policy.json": load_runtime_interpreter_policy,
    "config/sandbox_programmer_profiles.json": load_sandbox_programmer_profiles,
    "config/sandbox_release_policy.json": load_sandbox_release_policy,
    "config/semantic_resolution_rules.json": load_semantic_resolution_rules,
    "config/stage2_template_routes.json": load_stage2_template_routes,
}


def validate_config_mutation(
    *,
    root: Path,
    proposal_path: Path,
    write: bool = False,
) -> dict[str, Any]:
    base = root.resolve()
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    target = str(proposal.get("target") or "").replace("\\", "/")
    operation = str(proposal.get("operation") or "")
    report = {
        "artifact_type": "ConfigMutationSandboxReport",
        "status": "blocked",
        "root": base.as_posix(),
        "proposal_path": proposal_path.resolve().as_posix(),
        "target": target,
        "operation": operation,
        "target_modified": False,
        "validation": {},
    }
    if proposal.get("artifact_type") != "ConfigMutationProposal":
        report["validation"] = {"status": "failed", "errors": ["artifact_type_must_be_ConfigMutationProposal"]}
        return report
    if operation != "replace_file":
        report["validation"] = {"status": "failed", "errors": ["only_replace_file_is_supported"]}
        return report
    if target not in VALIDATORS:
        report["validation"] = {"status": "failed", "errors": [f"unsupported_target:{target}"]}
        return report
    target_path = (base / target).resolve()
    before = target_path.read_bytes() if target_path.is_file() else b""
    try:
        content = proposal["content"]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(content, handle, ensure_ascii=False, indent=2, sort_keys=True)
            temp_path = Path(handle.name)
        try:
            VALIDATORS[target](str(temp_path))
        finally:
            temp_path.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001 - sandbox reports validation failures.
        report["validation"] = {"status": "failed", "errors": [f"{type(exc).__name__}:{exc}"]}
        return report
    after = target_path.read_bytes() if target_path.is_file() else b""
    report["target_modified"] = before != after
    report["status"] = "passed" if not report["target_modified"] else "blocked"
    report["validation"] = {"status": "passed", "errors": []}
    if write:
        out = base / "artifacts" / "config_mutation_sandbox" / f"{target.replace('/', '__')}.report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = out.as_posix()
    return report
