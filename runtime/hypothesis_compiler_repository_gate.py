"""Repository-level rollback gate for compiled hypothesis promotion."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .promoted_candidate_selection_policies import load_selection_policies
from .self_improvement_hypothesis_compiler import load_hypothesis_compiler_config


Verifier = Callable[[Path], dict[str, Any]]
PROMOTION_PATHS = (
    Path("knowledge/role_knowledge/promoted_candidate_selection_policies.json"),
    Path("knowledge/role_knowledge/promoted_semantic_contract_profiles.json"),
    Path("knowledge/role_knowledge/promoted_executable_adapters.json"),
)


def capture_selection_state(root: Path) -> dict[Path, bytes | None]:
    return {
        relative: (root / relative).read_bytes() if (root / relative).exists() else None
        for relative in PROMOTION_PATHS
    }


def run_repository_gate(root: Path, verifier: Verifier | None = None) -> dict[str, Any]:
    if verifier:
        return dict(verifier(root))
    policy = dict(load_hypothesis_compiler_config().get("trial_policy") or {})
    gate = dict(policy.get("repository_regression_gate") or {})
    if not gate.get("enabled"):
        return {"status": "skipped", "reason": "repository_regression_gate_disabled"}
    command = [sys.executable, *[str(value) for value in gate.get("command") or []]]
    temp = root / ".pytest-tmp-hypothesis-repository-gate"
    temp.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "TEMP": str(temp), "TMP": str(temp)}
    try:
        completed = subprocess.run(
            command, cwd=root, env=environment, capture_output=True, text=True,
            timeout=float(gate["timeout_seconds"]), check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "blocked", "reason": "repository_regression_gate_timeout",
            "timeout_seconds": gate["timeout_seconds"], "output_tail": _tail(exc.stdout),
        }
    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
    return {
        "status": "passed" if completed.returncode == 0 else "blocked",
        "reason": None if completed.returncode == 0 else "repository_regression_gate_failed",
        "returncode": completed.returncode, "command": command[1:], "output_tail": _tail(output),
    }


def rollback_selection_state(root: Path, snapshot: dict[Path, bytes | None]) -> None:
    for relative, content in snapshot.items():
        path = root / relative
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)
    load_selection_policies.cache_clear()
    from .promoted_executable_adapters import load_executable_adapters
    from .promoted_semantic_contract_profiles import load_promoted_profiles
    load_executable_adapters.cache_clear()
    load_promoted_profiles.cache_clear()


def reject_promoted_result(result: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    admission = dict(result.get("admission") or {})
    evolution = dict(admission.get("evolution") or {})
    promotion = dict(evolution.get("promotion") or {})
    promotion.update({
        "applied": False, "rollback_applied": True,
        "status": "rejected", "reason": gate.get("reason"),
    })
    evolution.update({"promotion": promotion, "status": "blocked"})
    admission.update({
        "status": "blocked", "reason": gate.get("reason"),
        "promotion_applied": False, "evolution": evolution,
    })
    return {
        **result, "status": "blocked", "reason": gate.get("reason"),
        "admission": admission, "repository_regression_gate": gate,
        "rollback_applied": True,
    }


def _tail(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    return text[-limit:]
