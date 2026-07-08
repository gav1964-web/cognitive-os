"""Async DAG pipeline executor for the Cognitive OS runtime."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from .checkpoint import hash_payload, save_checkpoint
from .error_thresholds import increment_error_count
from .executor import _clear_plugin_modules, _execute_node, _registry_statuses
from .failure_log import append_failure_event
from .interrupt import build_interrupt
from .models import ExecutionContext, Pipeline, PipelineNode, RuntimeFailure
from .pipeline import topological_node_batches, validate_pipeline
from .policy_stub import decide
from .quarantine import classify_exception, should_quarantine, traceback_hash
from .registry import CapabilityRegistry


async def execute_pipeline_async(
    root: Path,
    pipeline: Pipeline,
    root_input: dict[str, Any],
    *,
    reset_registry: bool = False,
) -> dict[str, Any]:
    """Execute a validated Pipeline DSL as an asyncio-scheduled DAG.

    Nodes whose dependency edges are satisfied are launched in the same batch.
    A node failure pauses scheduling, records checkpoint/interrupt data, then
    applies the same deterministic policy path as the synchronous executor.
    """

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

    context = ExecutionContext(pipeline=pipeline, root_input=root_input, state="RUNNING")
    timeout_seconds = pipeline.retry_policy.get("node_timeout_seconds")
    timeout = float(timeout_seconds) if timeout_seconds is not None else None
    process_boundary = bool(pipeline.retry_policy.get("process_boundary", False))

    for batch in topological_node_batches(pipeline):
        tasks = {
            asyncio.create_task(
                _run_node(
                    root,
                    registry,
                    context,
                    node,
                    timeout=timeout,
                    process_boundary=process_boundary,
                )
            ): node
            for node in batch
        }
        results = await asyncio.gather(*tasks.keys(), return_exceptions=True)
        for task, result in zip(tasks, results):
            node = tasks[task]
            if isinstance(result, BaseException):
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                failure_result = await _handle_failure(root, registry, context, node, result)
                if failure_result is not None:
                    return failure_result
            context.node_outputs[node.id] = result
            context.completed_nodes.append(node.id)

    context.state = "STOPPED"
    return {"status": "ok", "state": context.state, "completed_nodes": context.completed_nodes, "outputs": context.node_outputs}


async def _run_node(
    root: Path,
    registry: CapabilityRegistry,
    context: ExecutionContext,
    node: PipelineNode,
    *,
    timeout: float | None,
    process_boundary: bool,
) -> dict[str, Any]:
    context.current_node = node.id
    call = asyncio.to_thread(
        _execute_node,
        registry,
        context,
        node.capability,
        node.input,
        root=root,
        process_boundary=process_boundary,
        timeout_seconds=timeout,
        node_id=node.id,
    )
    if timeout is None:
        return await call
    try:
        return await asyncio.wait_for(call, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"node timeout: {node.id}") from exc


async def _handle_failure(
    root: Path,
    registry: CapabilityRegistry,
    context: ExecutionContext,
    node: PipelineNode,
    exc: BaseException,
) -> dict[str, Any] | None:
    pipeline = context.pipeline
    capability_id = node.capability
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
        registry.mark_status(capability_id, "quarantined", reason=f"async_runtime_failure:{error_class}")
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

    timeout_seconds = pipeline.retry_policy.get("node_timeout_seconds")
    timeout = float(timeout_seconds) if timeout_seconds is not None else None
    process_boundary = bool(pipeline.retry_policy.get("process_boundary", False))
    if decision.action == "SWITCH_PLUGIN" and decision.replacement_capability:
        context.state = "ADAPTING"
        output = await _run_capability(
            root,
            registry,
            context,
            decision.replacement_capability,
            node.input,
            timeout=timeout,
            process_boundary=process_boundary,
        )
        context.node_outputs[node.id] = output
        context.completed_nodes.append(node.id)
        context.state = "RUNNING"
        return None

    if decision.action == "RETRY":
        retry_count = context.retry_counts.get(node.id, 0)
        max_attempts = int(pipeline.retry_policy.get("max_attempts", 1))
        registry.mark_status(capability_id, "degraded", reason=f"async_retry:{error_class}")
        if retry_count < max_attempts:
            context.retry_counts[node.id] = retry_count + 1
            context.state = "RUNNING"
            output = await _run_capability(
                root,
                registry,
                context,
                capability_id,
                node.input,
                timeout=timeout,
                process_boundary=process_boundary,
            )
            context.node_outputs[node.id] = output
            context.completed_nodes.append(node.id)
            context.state = "RUNNING"
            return None

    context.state = "STOPPED"
    return {
        "status": "stopped",
        "state": context.state,
        "interrupt": interrupt,
        "decision": decision.__dict__,
        "completed_nodes": context.completed_nodes,
        "outputs": context.node_outputs,
    }


async def _run_capability(
    root: Path,
    registry: CapabilityRegistry,
    context: ExecutionContext,
    capability_id: str,
    input_mapping: dict[str, Any],
    *,
    timeout: float | None,
    process_boundary: bool,
) -> dict[str, Any]:
    call = asyncio.to_thread(
        _execute_node,
        registry,
        context,
        capability_id,
        input_mapping,
        root=root,
        process_boundary=process_boundary,
        timeout_seconds=timeout,
        node_id=context.current_node,
    )
    if timeout is None:
        return await call
    try:
        return await asyncio.wait_for(call, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"node timeout: {context.current_node}") from exc
