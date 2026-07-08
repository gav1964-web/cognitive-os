"""Capability Registry persistence and lookup."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from types import TracebackType
from typing import Any

from .models import Capability
from .plugin_loader import load_capabilities
from .quality import load_quality_metrics
from .registry_events import append_registry_event


class CapabilityRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "registry" / "capabilities.json"
        self.lock_path = root / "registry" / "capabilities.lock"
        self.capabilities: dict[str, Capability] = {}

    def load(self) -> None:
        if not self.path.exists():
            self.reset_from_plugins()
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        loaded = load_capabilities(self.root)
        for item in data.get("capabilities", []):
            plugin_id = str(item["id"])
            if plugin_id not in loaded:
                continue
            base = loaded[plugin_id]
            self.capabilities[plugin_id] = Capability(
                **{**asdict(base), "lifecycle_status": str(item.get("lifecycle_status", base.lifecycle_status))}
            )

    def reset_from_plugins(self, *, reason: str = "reset_from_plugins") -> None:
        previous = {key: value.lifecycle_status for key, value in self.capabilities.items()}
        self.capabilities = load_capabilities(self.root)
        self.save()
        for capability_id, capability in sorted(self.capabilities.items()):
            old_status = previous.get(capability_id)
            if old_status != capability.lifecycle_status:
                append_registry_event(
                    self.root,
                    {
                        "event": "registry_status",
                        "capability_id": capability_id,
                        "old_status": old_status,
                        "new_status": capability.lifecycle_status,
                        "reason": reason,
                    },
                )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "capabilities": [
                _registry_record(capability)
                for capability in sorted(self.capabilities.values(), key=lambda item: item.id)
            ]
        }
        with self._write_lock():
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.{os.getpid()}.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp_path.replace(self.path)

    def get(self, capability_id: str) -> Capability:
        capability = self.capabilities[capability_id]
        if capability.lifecycle_status not in {"active", "degraded"}:
            raise RuntimeError(f"capability is not active: {capability_id}:{capability.lifecycle_status}")
        return capability

    def mark_status(self, capability_id: str, status: str, *, reason: str = "mark_status") -> None:
        current = self.capabilities[capability_id]
        old_status = current.lifecycle_status
        self.capabilities[capability_id] = Capability(**{**asdict(current), "lifecycle_status": status})
        self.save()
        if old_status != status:
            append_registry_event(
                self.root,
                {
                    "event": "registry_status",
                    "capability_id": capability_id,
                    "old_status": old_status,
                    "new_status": status,
                    "reason": reason,
                },
            )

    def find_fallback(self, failed_capability_id: str) -> Capability | None:
        failed = self.capabilities[failed_capability_id]
        candidates = [
            candidate
            for candidate in self.capabilities.values()
            if failed_capability_id in candidate.fallback_for
            and _schemas_compatible(failed.input_schema, candidate.input_schema)
            and _schemas_compatible(failed.output_schema, candidate.output_schema)
        ]
        return self.best_candidate(candidates)

    def candidates_for_contract(
        self,
        *,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
    ) -> list[Capability]:
        candidates = [
            capability
            for capability in self.capabilities.values()
            if _schemas_compatible(input_schema, capability.input_schema)
            and (output_schema is None or _schemas_compatible(output_schema, capability.output_schema))
        ]
        return sorted(candidates, key=self.score_capability, reverse=True)

    def best_candidate(self, candidates: list[Capability]) -> Capability | None:
        executable = [candidate for candidate in candidates if candidate.lifecycle_status in {"active", "degraded"}]
        if not executable:
            return None
        return sorted(executable, key=self.score_capability, reverse=True)[0]

    def score_capability(self, capability: Capability) -> tuple[int, int, int, int, int, str]:
        status_score = {"active": 2, "degraded": 1}.get(capability.lifecycle_status, 0)
        determinism_score = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}.get(capability.determinism_grade, 0)
        side_effect_score = _side_effect_score(capability.side_effects)
        quality = load_quality_metrics(self.root).get(capability.id, {})
        reliability_score = int((1.0 - float(quality.get("failure_rate", 0.0))) * 1000)
        latency_score = -int(float(quality.get("avg_latency_ms", 0.0)))
        return (status_score, determinism_score, side_effect_score, reliability_score, latency_score, capability.id)

    def selection_report(self) -> dict[str, Any]:
        quality_metrics = load_quality_metrics(self.root)
        rows = []
        for capability in sorted(self.capabilities.values(), key=self.score_capability, reverse=True):
            quality = quality_metrics.get(capability.id, {})
            rows.append(
                {
                    "id": capability.id,
                    "lifecycle_status": capability.lifecycle_status,
                    "determinism_grade": capability.determinism_grade,
                    "side_effects": capability.side_effects,
                    "quality": quality,
                    "score": list(self.score_capability(capability)),
                    "selectable": capability.lifecycle_status in {"active", "degraded"},
                }
            )
        return {"capabilities": rows}

    @contextmanager
    def _write_lock(self):
        lock = _RegistryLock(self.lock_path)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()


class _RegistryLock:
    def __init__(self, path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.fd: int | None = None

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"registry lock timeout: {self.path}")
                time.sleep(self.poll_seconds)

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "_RegistryLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def _registry_record(capability: Capability) -> dict[str, Any]:
    return {
        "id": capability.id,
        "version": capability.version,
        "entrypoint": capability.entrypoint,
        "input_schema_ref": capability.input_schema_ref,
        "output_schema_ref": capability.output_schema_ref,
        "determinism_grade": capability.determinism_grade,
        "side_effects": capability.side_effects,
        "lifecycle_status": capability.lifecycle_status,
        "version_hash": capability.version_hash,
        "fallback_for": capability.fallback_for,
    }


def _schemas_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left == right


def _side_effect_score(side_effects: dict[str, Any]) -> int:
    score = 0
    if side_effects.get("filesystem") == "none":
        score += 2
    elif side_effects.get("filesystem") in {"read_only", "write_scoped"}:
        score += 1
    if side_effects.get("network") == "none":
        score += 2
    if side_effects.get("secrets") == "none":
        score += 2
    return score
