"""Frozen three-route evaluation protocol and blind evidence packaging."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROUTES = ("direct_agent", "short_chain", "full_chain")
RECEIPT_STATUSES = {"completed", "blocked", "failed"}
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
INPUT_SKIP_DIRS = {
    ".git", ".hg", ".mypy_cache", ".pytest_cache", ".tox", ".venv",
    "__pycache__", "node_modules", "venv",
}


def freeze_manifest(root: Path, *, source_commit: str, task_names: list[str] | None = None) -> dict[str, Any]:
    evaluation = root / "evaluation"
    names = task_names or [
        path.name for path in sorted(evaluation.glob("task*"))
        if path.is_dir() and path.name != "task_template"
    ]
    tasks = [_freeze_task(root.resolve(), evaluation / name) for name in names]
    payload = {
        "artifact_type": "ThreeRouteEvaluationManifest",
        "schema_version": "three_route_evaluation_manifest.v2",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "routes": list(ROUTES),
        "tasks": tasks,
        "authority": {
            "legacy_metrics": "non_authoritative",
            "route_self_scores": "forbidden",
            "winner_requires_independent_blind_score": True,
        },
    }
    payload["manifest_digest"] = _digest(payload)
    return payload


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    supplied = str(manifest.get("manifest_digest") or "")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    if supplied != _digest(unsigned):
        errors.append("manifest_digest_mismatch")
    if tuple(manifest.get("routes") or []) != ROUTES:
        errors.append("routes_must_be_direct_short_full")
    tasks = list(manifest.get("tasks") or [])
    if len({str(row.get("task_id")) for row in tasks}) != len(tasks):
        errors.append("duplicate_task_id")
    for row in tasks:
        if not row.get("task_id") or not row.get("prompt_digest") or not row.get("task_class"):
            errors.append(f"incomplete_task:{row.get('task_id')}")
        if not DIGEST_PATTERN.fullmatch(str(row.get("input_digest") or "")):
            errors.append(f"invalid_input_digest:{row.get('task_id')}")
        if not row.get("prompt_text"):
            errors.append(f"empty_prompt:{row.get('task_id')}")
    return errors


def manifest_drift_errors(
    root: Path, manifest: dict[str, Any], *, allow_missing_external_inputs: bool = False
) -> list[str]:
    errors = list(validate_manifest(manifest))
    expected = {str(row.get("task_id")): row for row in manifest.get("tasks", [])}
    actual_names = {
        path.name for path in (root / "evaluation").glob("task*")
        if path.is_dir() and path.name != "task_template"
    }
    if actual_names != set(expected):
        errors.append("manifest_task_set_drift")
    for task_id in sorted(actual_names & set(expected)):
        try:
            current = _freeze_task(root.resolve(), root / "evaluation" / task_id)
        except ValueError as exc:
            if allow_missing_external_inputs and "evaluation input project is missing" in str(exc):
                current, expected_inputs = _task_definition(root / "evaluation" / task_id)
                declared = json.loads((root / "evaluation" / task_id / "input.json").read_text(encoding="utf-8"))
                expected_base = {
                    key: value for key, value in expected[task_id].items()
                    if key not in {"input_spec", "input_digest"}
                }
                expected_spec = {
                    key: value for key, value in dict(expected[task_id]["input_spec"]).items()
                    if key != "tree_digest"
                }
                if current != expected_base or expected_inputs != current["expected_inputs"] or declared != expected_spec:
                    errors.append(f"task_snapshot_drift:{task_id}")
                continue
            errors.append(f"task_snapshot_unreadable:{task_id}:{type(exc).__name__}")
            continue
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"task_snapshot_unreadable:{task_id}:{type(exc).__name__}")
            continue
        if current != expected[task_id]:
            errors.append(f"task_snapshot_drift:{task_id}")
    return sorted(set(errors))


def validate_receipt(
    receipt: dict[str, Any], manifest: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    tasks = {str(row["task_id"]): row for row in manifest.get("tasks", [])}
    task_id = str(receipt.get("task_id") or "")
    route = str(receipt.get("route") or "")
    task = tasks.get(task_id)
    if task is None:
        errors.append("unknown_task")
    if route not in ROUTES:
        errors.append("unknown_route")
    if receipt.get("manifest_digest") != manifest.get("manifest_digest"):
        errors.append("manifest_digest_mismatch")
    if task and receipt.get("prompt_digest") != task.get("prompt_digest"):
        errors.append("prompt_digest_mismatch")
    if not DIGEST_PATTERN.fullmatch(str(receipt.get("input_digest") or "")):
        errors.append("invalid_input_digest")
    elif task and receipt.get("input_digest") != task.get("input_digest"):
        errors.append("input_digest_mismatch")
    if receipt.get("status") not in RECEIPT_STATUSES:
        errors.append("invalid_status")
    for field in ("executor", "model", "runtime_seconds", "estimated_cost", "token_usage"):
        if receipt.get(field) is None:
            errors.append(f"missing_{field}")
    for field in ("runtime_seconds", "estimated_cost"):
        value = receipt.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            errors.append(f"invalid_{field}")
    token_usage = receipt.get("token_usage")
    if not isinstance(token_usage, dict) or any(
        not isinstance(token_usage.get(name), int)
        or isinstance(token_usage.get(name), bool)
        or token_usage[name] < 0
        for name in ("input", "output")
    ):
        errors.append("invalid_token_usage")
    for field in ("manual_corrections", "acceptance_checks", "artifacts"):
        if not isinstance(receipt.get(field), list):
            errors.append(f"{field}_must_be_list")
    for correction in receipt.get("manual_corrections") or []:
        if (
            not isinstance(correction, dict)
            or not correction.get("kind")
            or not isinstance(correction.get("minutes"), (int, float))
        ):
            errors.append("invalid_manual_correction")
    for artifact in receipt.get("artifacts") or []:
        if (
            not isinstance(artifact, dict)
            or not artifact.get("path")
            or not DIGEST_PATTERN.fullmatch(str(artifact.get("digest") or ""))
        ):
            errors.append("invalid_artifact_evidence")
    if not isinstance(receipt.get("judge_payload"), dict):
        errors.append("judge_payload_must_be_object")
    safety = receipt.get("safety")
    if not isinstance(safety, dict) or "source_mutation_detected" not in safety:
        errors.append("incomplete_safety_evidence")
    route_policy = dict(dict(policy.get("route_contracts") or {}).get(route) or {})
    executor = str(receipt.get("executor") or "").lower()
    if any(value.lower() in executor for value in route_policy.get("forbidden_executors", [])):
        errors.append("forbidden_route_executor")
    if route_policy.get("may_use_cognitive_os") is False and receipt.get("uses_cognitive_os") is not False:
        errors.append("direct_route_cognitive_os_use_forbidden")
    return sorted(set(errors))


def build_blind_bundle(
    manifest: dict[str, Any], receipts: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = validate_manifest(manifest)
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for receipt in receipts:
        receipt_errors = validate_receipt(receipt, manifest, policy)
        if receipt_errors:
            errors.extend(f"{receipt.get('task_id')}:{receipt.get('route')}:{item}" for item in receipt_errors)
            continue
        key = (str(receipt["task_id"]), str(receipt["route"]))
        if key in indexed:
            errors.append(f"duplicate_receipt:{key[0]}:{key[1]}")
        indexed[key] = receipt
    candidates = []
    mapping = []
    blind_secret = secrets.token_bytes(32)
    for task in manifest.get("tasks", []):
        task_id = str(task["task_id"])
        task_receipts = [indexed.get((task_id, route)) for route in ROUTES]
        models = {str(row.get("model")) for row in task_receipts if row is not None}
        if policy.get("require_same_model_per_task") and len(models) > 1:
            errors.append(f"model_mismatch:{task_id}")
        input_digests = {str(row.get("input_digest")) for row in task_receipts if row is not None}
        if len(input_digests) > 1:
            errors.append(f"input_snapshot_mismatch:{task_id}")
        for route in ROUTES:
            receipt = indexed.get((task_id, route))
            if receipt is None:
                errors.append(f"missing_receipt:{task_id}:{route}")
                continue
            candidate_id = _candidate_id(blind_secret, task_id, route)
            candidates.append({
                "task_id": task_id,
                "task_class": task["task_class"],
                "candidate_id": candidate_id,
                "status": receipt["status"],
                "judge_payload": _redact(receipt["judge_payload"]),
                "acceptance_checks": _redact(receipt["acceptance_checks"]),
                "safety": receipt["safety"],
            })
            mapping.append({"task_id": task_id, "candidate_id": candidate_id, "route": route})
    if errors:
        raise ValueError("blind bundle rejected: " + "; ".join(sorted(set(errors))))
    bundle = {
        "artifact_type": "ThreeRouteBlindBundle",
        "schema_version": "three_route_blind_bundle.v2",
        "manifest_digest": manifest["manifest_digest"],
        "rubric": policy["rubric"],
        "tasks": [
            {
                "task_id": row["task_id"], "task_class": row["task_class"],
                "prompt": row["prompt_text"], "constraints": row["constraints"],
                "expected_inputs": row["expected_inputs"], "input_spec": row["input_spec"],
                "input_digest": row["input_digest"], "success_criteria": row["success_criteria"],
            }
            for row in manifest.get("tasks", [])
        ],
        "candidates": sorted(candidates, key=lambda row: (row["task_id"], row["candidate_id"])),
    }
    bundle["bundle_digest"] = _digest(bundle)
    key = {
        "artifact_type": "ThreeRouteBlindKey",
        "bundle_digest": bundle["bundle_digest"],
        "mapping": mapping,
    }
    key["key_digest"] = _digest(key)
    return bundle, key


def protocol_status(
    manifest: dict[str, Any], receipts: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    valid = {(str(row.get("task_id")), str(row.get("route"))) for row in receipts if not validate_receipt(row, manifest, policy)}
    tasks = [str(row["task_id"]) for row in manifest.get("tasks", [])]
    complete = [task for task in tasks if all((task, route) in valid for route in ROUTES)]
    product_classes = set(policy.get("product_task_classes") or [])
    task_classes = {str(row["task_id"]): str(row["task_class"]) for row in manifest.get("tasks", [])}
    product_tasks = [task for task in tasks if task_classes[task] in product_classes]
    product_complete = [task for task in complete if task_classes[task] in product_classes]
    class_counts = {
        task_class: sum(task_classes[task] == task_class for task in product_complete)
        for task_class in sorted(product_classes)
    }
    class_minimum = int(policy.get("minimum_tasks_per_class_before_claim", 2))
    class_coverage_ok = all(value >= class_minimum for value in class_counts.values())
    coverage = {route: sum((task, route) in valid for task in tasks) for route in ROUTES}
    minimum = int(policy.get("minimum_tasks_before_claim", 20))
    return {
        "artifact_type": "ThreeRouteEvaluationStatus",
        "status": "ready_for_blind_judging" if len(complete) == len(tasks) and tasks else "evidence_required",
        "manifest_digest": manifest.get("manifest_digest"),
        "task_count": len(tasks),
        "complete_three_route_tasks": len(complete),
        "product_task_count": len(product_tasks),
        "complete_product_tasks": len(product_complete),
        "ablation_task_count": len(tasks) - len(product_tasks),
        "route_receipt_coverage": coverage,
        "product_class_counts": class_counts,
        "class_coverage_ok": class_coverage_ok,
        "claim_eligible": len(product_complete) >= minimum and class_coverage_ok,
        "missing": [f"{task}:{route}" for task in tasks for route in ROUTES if (task, route) not in valid],
    }


def load_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(item.read_text(encoding="utf-8")) for item in sorted(path.glob("*.json"))]


def _freeze_task(root: Path, task_dir: Path) -> dict[str, Any]:
    row, expected_inputs = _task_definition(task_dir)
    input_spec, input_digest = _freeze_input(root, task_dir, expected_inputs)
    return {**row, "input_spec": input_spec, "input_digest": input_digest}


def _task_definition(task_dir: Path) -> tuple[dict[str, Any], list[str]]:
    prompt_path = task_dir / "prompt.md"
    metrics_path = task_dir / "metrics.json"
    text = prompt_path.read_text(encoding="utf-8")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    prompt = _section(text, ("Original Prompt", "Prompt"))
    expected_inputs = _bullets(_section(text, ("Expected Inputs",)))
    return {
        "task_id": task_dir.name,
        "task_class": str(metrics.get("task_class") or "unknown"),
        "task_file_digest": _bytes_digest(prompt_path.read_bytes()),
        "prompt_digest": _bytes_digest(prompt.encode("utf-8")),
        "prompt_text": prompt,
        "constraints": _bullets(_section(text, ("Constraints",))),
        "expected_inputs": expected_inputs,
        "success_criteria": _bullets(_section(text, ("Success Criteria",))),
    }, expected_inputs


def _freeze_input(root: Path, task_dir: Path, expected_inputs: list[str]) -> tuple[dict[str, Any], str]:
    path = task_dir / "input.json"
    if not path.exists():
        spec = {"kind": "declared_prompt_inputs", "expected_inputs": expected_inputs}
        return spec, _digest(spec)
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("kind") != "project_tree":
        return spec, _digest(spec)
    source = (root / str(spec.get("path") or "")).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"evaluation input escapes workspace: {source}") from exc
    if not source.is_dir():
        raise ValueError(f"evaluation input project is missing: {source}")
    frozen = dict(spec)
    frozen["tree_digest"] = _tree_digest(source)
    return frozen, _digest(frozen)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in INPUT_SKIP_DIRS for part in relative.parts):
            continue
        label = relative.as_posix().encode("utf-8")
        if path.is_symlink():
            digest.update(b"L\0" + label + b"\0" + str(path.readlink()).encode("utf-8") + b"\0")
        elif path.is_file():
            digest.update(b"F\0" + label + b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _section(text: str, names: tuple[str, ...]) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## ") and line.removeprefix("## ").strip() in names:
            body = []
            for value in lines[index + 1:]:
                if value.startswith("## "):
                    break
                body.append(value)
            return "\n".join(body).strip()
    return ""


def _bullets(text: str) -> list[str]:
    return [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith("- ")]


def _candidate_id(blind_secret: bytes, task_id: str, route: str) -> str:
    message = f"{task_id}:{route}".encode("utf-8")
    return "candidate_" + hmac.new(blind_secret, message, hashlib.sha256).hexdigest()[:16]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items() if key not in {"executor", "model", "route"}}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for label in ("Cognitive OS", "cognitive_os", "direct agent", "direct_agent", "short chain", "full chain"):
            result = result.replace(label, "[route]").replace(label.title(), "[route]")
        return result
    return value


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
