"""Pipeline executor for the Cognitive OS MVP."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from .checkpoint import hash_payload, load_checkpoint, save_checkpoint
from .error_thresholds import increment_error_count
from .execution_journal import append_journal_event
from .failure_log import append_failure_event
from .interrupt import build_interrupt
from .models import ExecutionContext, Pipeline, RuntimeFailure
from .pipeline import resolve_node_input, topological_nodes, validate_pipeline
from .plugin_loader import load_entrypoint
from .policy_stub import decide
from .process_runner import run_entrypoint_in_process
from .quality import record_quality_event
from .quarantine import classify_exception, should_quarantine, traceback_hash
from .registry import CapabilityRegistry
from .schema import SchemaValidationError, validate_payload


def execute_pipeline(root: Path, pipeline: Pipeline, root_input: dict[str, Any], *, reset_registry: bool = False) -> dict[str, Any]:
    return _execute_pipeline_context(
        root,
        pipeline,
        ExecutionContext(pipeline=pipeline, root_input=root_input, state="RUNNING"),
        reset_registry=reset_registry,
    )


def resume_pipeline(
    root: Path,
    checkpoint_id: str,
    *,
    pipeline: Pipeline | None = None,
    reset_registry: bool = False,
) -> dict[str, Any]:
    checkpoint = load_checkpoint(root, checkpoint_id)
    if pipeline is None:
        from .pipeline import load_pipeline

        pipeline = load_pipeline(root / "pipelines" / f"{checkpoint['pipeline_id']}.json")
    context = ExecutionContext(
        pipeline=pipeline,
        root_input=dict(checkpoint["root_input"]),
        state="RUNNING",
        current_node=str(checkpoint.get("current_node") or ""),
        completed_nodes=[str(item) for item in checkpoint.get("completed_nodes", [])],
        node_outputs={
            str(node_id): dict(payload["output"])
            for node_id, payload in dict(checkpoint.get("node_outputs", {})).items()
        },
    )
    append_journal_event(
        root,
        {
            "event": "pipeline_resumed",
            "pipeline_id": pipeline.id,
            "checkpoint_id": checkpoint_id,
            "completed_nodes": context.completed_nodes,
        },
    )
    return _execute_pipeline_context(root, pipeline, context, reset_registry=reset_registry)


def _execute_pipeline_context(
    root: Path,
    pipeline: Pipeline,
    context: ExecutionContext,
    *,
    reset_registry: bool,
) -> dict[str, Any]:
    root_text = str(root)
    sys.path = [item for item in sys.path if item != root_text]
    sys.path.insert(0, root_text)
    _clear_plugin_modules()

    registry = CapabilityRegistry(root)
    if reset_registry:
        registry.reset_from_plugins()
    else:
        registry.load()
    validate_pipeline(pipeline, registry)

    context.state = "RUNNING"
    process_boundary = bool(pipeline.retry_policy.get("process_boundary", False))
    timeout_seconds = pipeline.retry_policy.get("node_timeout_seconds")
    timeout = float(timeout_seconds) if timeout_seconds is not None else None
    ordered_nodes = topological_nodes(pipeline)
    for node in ordered_nodes:
        if node.id in context.completed_nodes:
            continue
        context.current_node = node.id
        capability_id = node.capability
        try:
            output = _execute_node(
                registry,
                context,
                capability_id,
                node.input,
                root=root,
                process_boundary=process_boundary,
                timeout_seconds=timeout,
            )
            context.node_outputs[node.id] = output
            context.completed_nodes.append(node.id)
        except Exception as exc:
            error_class, exception_type = classify_exception(exc)
            failure = RuntimeFailure(
                error_class=error_class,
                exception_type=exception_type,
                message=str(exc),
                traceback_hash=traceback_hash(exc),
            )
            context.state = "PAUSED"
            repeated_count = increment_error_count(
                root,
                capability_id=capability_id,
                error_class=error_class,
                fingerprint=failure.traceback_hash,
            )
            status = "active"
            if should_quarantine(error_class, repeated_count=repeated_count):
                registry.mark_status(capability_id, "quarantined", reason=f"runtime_failure:{error_class}")
                status = "quarantined"
            checkpoint_id = save_checkpoint(root, context, registry_hash=hash_payload(_registry_statuses(registry)))
            interrupt = build_interrupt(
                root=root,
                pipeline_id=pipeline.id,
                failed_node_id=node.id,
                capability_id=capability_id,
                failure=failure,
                state_ref=checkpoint_id,
                capability_status=status,
                suggested_actions=["RETRY", "SWITCH_PLUGIN", "GENERATE_SPEC", "STOP"],
                input_payload=context.root_input,
                version_hash=registry.capabilities[capability_id].version_hash,
            )
            context.state = "INTERRUPTED"
            decision = decide(interrupt, registry)
            append_failure_event(
                root,
                {
                    "pipeline_id": pipeline.id,
                    "failed_node_id": node.id,
                    "capability_id": capability_id,
                    "error_class": failure.error_class,
                    "exception_type": failure.exception_type,
                    "traceback_hash": failure.traceback_hash,
                    "repeated_count": repeated_count,
                    "checkpoint_id": checkpoint_id,
                    "capability_status": status,
                    "decision": decision.__dict__,
                },
            )
            if decision.action == "SWITCH_PLUGIN" and decision.replacement_capability:
                context.state = "ADAPTING"
                output = _execute_node(
                    registry,
                    context,
                    decision.replacement_capability,
                    node.input,
                    root=root,
                    process_boundary=process_boundary,
                    timeout_seconds=timeout,
                )
                context.node_outputs[node.id] = output
                context.completed_nodes.append(node.id)
                context.state = "RUNNING"
                continue
            if decision.action == "RETRY":
                retry_count = context.retry_counts.get(node.id, 0)
                max_attempts = int(pipeline.retry_policy.get("max_attempts", 1))
                registry.mark_status(capability_id, "degraded", reason=f"retry:{error_class}")
                if retry_count < max_attempts:
                    context.retry_counts[node.id] = retry_count + 1
                    context.state = "RUNNING"
                    output = _execute_node(
                        registry,
                        context,
                        capability_id,
                        node.input,
                        root=root,
                        process_boundary=process_boundary,
                        timeout_seconds=timeout,
                    )
                    context.node_outputs[node.id] = output
                    context.completed_nodes.append(node.id)
                    continue
            context.state = "STOPPED"
            return {
                "status": "stopped",
                "state": context.state,
                "interrupt": interrupt,
                "decision": decision.__dict__,
                "completed_nodes": context.completed_nodes,
                "outputs": context.node_outputs,
            }
    context.state = "STOPPED"
    return {"status": "ok", "state": context.state, "completed_nodes": context.completed_nodes, "outputs": context.node_outputs}


def _execute_node(
    registry: CapabilityRegistry,
    context: ExecutionContext,
    capability_id: str,
    input_mapping: dict[str, Any],
    *,
    root: Path | None = None,
    process_boundary: bool = False,
    timeout_seconds: float | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    capability = registry.get(capability_id)
    journal_node_id = node_id or context.current_node
    node_input = resolve_node_input(context, input_mapping)
    validate_payload(node_input, capability.input_schema, label=f"{capability.id}.input")
    if root is not None:
        append_journal_event(
            root,
            {
                "event": "node_started",
                "pipeline_id": context.pipeline.id,
                "node_id": journal_node_id,
                "capability_id": capability_id,
            },
        )
    start = time.perf_counter()
    try:
        if process_boundary:
            if root is None:
                raise RuntimeError("process boundary requires workspace root")
            output = run_entrypoint_in_process(root, capability.entrypoint, node_input, timeout_seconds=timeout_seconds)
        else:
            fn = load_entrypoint(capability.entrypoint)
            output = fn(node_input)
        if not isinstance(output, dict):
            raise SchemaValidationError(f"{capability.id}.output must be object")
        validate_payload(output, capability.output_schema, label=f"{capability.id}.output")
        latency_ms = (time.perf_counter() - start) * 1000
        if root is not None:
            record_quality_event(root, capability_id=capability_id, success=True, latency_ms=latency_ms)
            append_journal_event(
                root,
                {
                    "event": "node_completed",
                    "pipeline_id": context.pipeline.id,
                    "node_id": journal_node_id,
                    "capability_id": capability_id,
                    "latency_ms": latency_ms,
                },
            )
        return output
    except Exception:
        latency_ms = (time.perf_counter() - start) * 1000
        if root is not None:
            record_quality_event(root, capability_id=capability_id, success=False, latency_ms=latency_ms)
            append_journal_event(
                root,
                {
                    "event": "node_failed",
                    "pipeline_id": context.pipeline.id,
                    "node_id": journal_node_id,
                    "capability_id": capability_id,
                    "latency_ms": latency_ms,
                },
            )
        raise


def _registry_statuses(registry: CapabilityRegistry) -> dict[str, str]:
    return {key: value.lifecycle_status for key, value in sorted(registry.capabilities.items())}


def _clear_plugin_modules() -> None:
    for name in list(sys.modules):
        if name == "plugins" or name.startswith("plugins."):
            sys.modules.pop(name, None)
