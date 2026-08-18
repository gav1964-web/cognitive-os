"""Execute bounded positive acceptance samples and report concise failures."""

from __future__ import annotations

import asyncio
import inspect
import io
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from .executable_acceptance_materializers import materialize


def positive_samples_execute(
    func: object,
    target: str,
    obligations: list[dict[str, Any]],
    mapping: dict[str, str] | None = None,
    defaults: dict[str, Any] | None = None,
    drop_surplus_payload: bool = False,
    diagnostics: list[str] | None = None,
) -> bool:
    seen: set[str] = set()
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        marker = repr((row.get("given", {}), row.get("expect", {})))
        if marker in seen:
            continue
        seen.add(marker)
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                given = _mapped_given(dict(row.get("given", {})), mapping or {}, drop_surplus_payload)
                payload = {**dict(defaults or {}), **given}
                args, kwargs = _call_args_kwargs(func, materialize(payload))
                try:
                    asyncio.get_event_loop()
                except RuntimeError:
                    asyncio.set_event_loop(asyncio.new_event_loop())
                result = func(*args, **kwargs)
                if isinstance(result, asyncio.Future) and result.done():
                    result = result.result()
                elif inspect.isawaitable(result):
                    result = asyncio.run(result)
                expect = dict(row.get("expect") or {})
                if not _positive_result_matches_expect(result, expect):
                    _record(diagnostics, f"expected={expect!r}; got={result!r}")
                    return False
        except (Exception, SystemExit) as exc:
            _record(diagnostics, f"{type(exc).__name__}: {str(exc)}")
            return False
    return True


def _record(diagnostics: list[str] | None, value: str) -> None:
    if diagnostics is not None:
        diagnostics.append(value[:500])


def _positive_result_matches_expect(result: Any, expect: dict[str, Any]) -> bool:
    if expect == {"completed": True}:
        return result is None or result is True or isinstance(result, dict)
    if any(key in expect for key in ("return_value", "equals", "result_value")):
        key = next(key for key in ("return_value", "equals", "result_value") if key in expect)
        return result == expect[key]
    if set(expect) == {"result"}:
        return _matches_declared_result(result, str(expect.get("result") or ""))
    return True


def _matches_declared_result(result: Any, declared: str) -> bool:
    if isinstance(result, dict) and "result" in result:
        return _matches_declared_result(result["result"], declared)
    normalized = declared.lower()
    compact = normalized.replace(" ", "")
    allows_none = "optional[" in compact or "nonetype" in compact or "|none" in compact
    if result is None and allows_none:
        return True
    if normalized in {"str", "string"}:
        return isinstance(result, str)
    if normalized in {"int", "integer"}:
        return isinstance(result, int) and not isinstance(result, bool)
    if normalized in {"bool", "boolean"}:
        return isinstance(result, bool)
    if normalized in {"list", "array", "sequence"}:
        return isinstance(result, list)
    if normalized in {"dict", "mapping", "object"}:
        return isinstance(result, dict)
    if normalized in {"any", "inferredoutput", "inferred_output"}:
        return True
    if normalized in {"none", "null", "void"}:
        return result is None
    return result is not None


def _mapped_given(
    given: dict[str, Any], mapping: dict[str, str], drop_surplus_payload: bool = False
) -> dict[str, Any]:
    if drop_surplus_payload:
        return {}
    if not mapping:
        return given
    return {actual: given[source] for actual, source in mapping.items() if source in given}


def _call_args_kwargs(func: object, payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return [], payload
    args: list[Any] = []
    kwargs = dict(payload)
    for name, param in signature.parameters.items():
        if param.kind == inspect.Parameter.POSITIONAL_ONLY and name in kwargs:
            args.append(kwargs.pop(name))
    return args, kwargs
