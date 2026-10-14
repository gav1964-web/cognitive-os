"""Base constructor sample values for exception-pickle replay."""

from __future__ import annotations

from typing import Any

def _sample_constructor_value(name: str, *, object_contracts: dict[str, Any] | None = None) -> Any:
    lowered = name.lower()
    string_names = {
        "value",
        "message",
        "msg",
        "action",
        "host",
        "url",
        "name",
        "lookup",
        "f",
        "reason",
        "schema_name",
        "new_type",
        "existing_type",
        "command",
        "kind",
        "key",
        "env_var",
        "provider_name",
        "model_id",
        "operation",
        "repo_path",
        "method_name",
        "driver_name",
        "dir",
        "extra_name",
        "package_name",
        "filename",
        "path",
        "field",
        "option",
        "source",
        "sim_id",
        "storage_key",
        "found_version",
        "max_supported_version",
        "version",
        "code",
        "model_name",
        "api_class_name",
        "argument",
        "captcha_sid",
        "captcha_img",
        "connection_name",
        "detail",
        "message_type",
        "block_type",
        "description",
        "subject",
        "todo_id",
        "sid",
        "status",
        "ad_title",
        "current",
        "expected",
        "actual",
        "type_",
        "summary",
        "address",
        "filepath",
        "var_name",
        "got_type",
        "resource_type",
        "property_name",
        "ad_id",
        "txn_id",
        "table_name",
        "shared_lib_path",
        "error_type",
        "connection_id",
        "import_name",
        "func_name",
        "task_name",
        "guild_id",
        "service_name",
        "job_id",
        "stream_name",
        "auth_url",
        "file_path",
        "error_message",
        "output",
        "endpoint",
        "rev",
        "domain",
        "service",
        "lower",
        "upper",
    }
    if lowered in string_names:
        return f"sample-{lowered}"
    if lowered.endswith(("_filepath", "_file_path")):
        return f"sample-{lowered}.py"
    integer_names = {
        "status_code",
        "exit_code",
        "position",
        "port",
        "max_bytes",
        "limit",
        "used",
        "cap",
        "returncode",
        "retry_count",
        "timeout_seconds",
        "step_index",
        "return_code",
        "lineno",
        "maximum",
        "minimum",
        "requested_size",
        "remaining_size",
        "pending_bytes",
        "step_time",
        "current_step_time",
        "last_step_time",
        "next_step_time",
        "output_time",
        "progress_time",
        "max_loop_iterations",
        "retry_after",
        "max_length",
        "line",
        "column",
        "index",
        "total",
        "count",
        "size",
        "amount",
        "number",
        "source_count",
        "failure_count",
    }
    if lowered in integer_names:
        return 7
    if lowered in {"data", "payload", "response_text", "stdout", "stderr", "unparsed_data", "params", "context"}:
        return f"sample-{lowered}"
    if lowered in {"messages", "defects", "possible_specs", "errors", "literals", "converters", "available_models", "pending_messages", "error_items", "requirement_chain", "requirements", "issues", "values", "parse_errors", "parents", "ref_infos", "topics", "heads", "missing_services"}:
        return [f"sample-{lowered}"]
    if lowered == "stages":
        return [
            {
                "__sample__": "named_object",
                "name": "sample-stage-one",
                "relpath": "stage-one.dvc",
                "addressing": "stage-one.dvc",
            },
            {
                "__sample__": "named_object",
                "name": "sample-stage-two",
                "relpath": "stage-two.dvc",
                "addressing": "stage-two.dvc",
            },
        ]
    if lowered == "dependents":
        return [{"__sample__": "format_object", "value": "sample-dependent"}]
    if lowered in {"param", "type", "flag", "opt_type", "transformer", "instance"}:
        payload = {
            "__sample__": "named_object",
            "name": f"sample-{lowered}",
            "mention": f"<sample-{lowered}>",
        }
        if lowered == "param":
            payload["displayed_name"] = f"sample-{lowered}"
        if lowered == "flag":
            payload["max_args"] = 1
            payload["annotation"] = "sample-annotation"
        if lowered == "transformer":
            payload["_error_display_name"] = f"sample-{lowered}"
        return payload
    if lowered == "cooldown":
        return {"__sample__": "cooldown", "rate": 1, "per": 2.0}
    if lowered in {"repo_path", "receipt_path", "fallback_receipt_path"}:
        return {"__sample__": "path", "value": f"sample-{lowered}"}
    if lowered in {"error", "cause", "original", "original_error", "exception", "driver_error"}:
        return {"__sample__": "exception", "message": f"sample-{lowered}"}
    if lowered == "os_error":
        return {"__sample__": "os_error", "errno": 7, "message": "sample-os-error"}
    if lowered == "span":
        return [0, 6]
    if lowered == "connection_key":
        return {
            "__sample__": "named_object",
            "name": "sample-connection-key",
            "mention": "<sample-connection-key>",
            "host": "sample-host",
            "port": 443,
            "ssl": True,
        }
    if lowered == "bucket":
        return {
            "__sample__": "named_object",
            "name": "sample-bucket",
            "mention": "<sample-bucket>",
            "window": 7,
        }
    if lowered == "response":
        return {
            "__sample__": "response",
            "status_code": 400,
            "url": "https://example.invalid/sample",
            "content": '{"error": "sample-error"}',
            "text": '{"error": "sample-error"}',
            "json": {"error": "sample-error"},
        }
    if lowered == "container":
        return {
            "__sample__": "named_object",
            "name": "sample-container",
            "mention": "<sample-container>",
        }
    if lowered == "failed_step":
        return {
            "__sample__": "named_object",
            "name": "sample-step",
            "mention": "<sample-step>",
        }
    if lowered == "replacement_state":
        return {"before": "sample-before", "after": "sample-after"}
    if lowered in {"receipt"}:
        return {"id": "sample-receipt"}
    if lowered == "record":
        return {"id": "sample-record"}
    if lowered == "content":
        return {"__sample__": "bytes", "value": "sample-content"}
    if lowered == "auth_message":
        return "sample-auth-message"
    if lowered == "spec":
        return {"__sample__": "format_object", "value": "sample-spec"}
    if lowered == "exceptions":
        return {"sample-objective": [{"__sample__": "exception", "message": "sample-exception"}, ["sample-traceback"]]}
    if lowered == "scored_successfully":
        return {"sample-objective": 1.0}
    if lowered == "hint_stmt":
        return "sample-hint"
    if lowered == "excinfo":
        return {
            "__sample__": "excinfo",
            "formatted": "RuntimeError: sample failure",
            "msg": "sample failure",
            "errdisplay": "sample traceback",
        }
    contract = dict(dict(object_contracts or {}).get(name) or {})
    kind = str(contract.get("contract_kind") or "")
    if kind == "string_like":
        return f"sample-{lowered}"
    if kind == "iterable_string_list":
        return [f"sample-{lowered}"]
    if kind == "attribute_object":
        evidence = dict(contract.get("evidence") or {})
        attributes = [
            str(value)
            for value in evidence.get("attributes") or []
            if str(value).isidentifier() and not str(value).startswith("_")
        ]
        payload = {
            "__sample__": "named_object",
            "name": f"sample-{lowered}",
            "mention": f"<sample-{lowered}>",
        }
        for attribute in attributes:
            payload.setdefault(attribute, f"sample-{attribute}")
        return payload
    if kind == "mapping_object":
        evidence = dict(contract.get("evidence") or {})
        keys = [
            str(value)
            for value in evidence.get("mapping_keys") or []
            if str(value) and not str(value).startswith("_")
        ]
        if not keys or len(keys) > 8:
            return None
        return {key: f"sample-{key}" for key in keys}
    if kind == "method_object":
        evidence = dict(contract.get("evidence") or {})
        methods = {}
        profiles = dict(evidence.get("method_return_profiles") or {})
        for method in [str(value) for value in evidence.get("method_calls") or []]:
            profile = str(profiles.get(method) or "")
            if profile == "mapping":
                methods[method] = {"message": f"sample-{lowered}", "status": "sample-status"}
            elif profile == "string":
                methods[method] = f"sample-{lowered}"
        if not methods or len(methods) > 3:
            return None
        return {"__sample__": "method_object", "methods": methods}
    return None
