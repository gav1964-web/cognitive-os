"""Error classification and quarantine policy."""

from __future__ import annotations

import hashlib
import traceback

from .schema import SchemaValidationError
from .process_runner import ProcessExecutionError


def classify_exception(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, ProcessExecutionError):
        child_type = exc.exception_type
        if child_type in {"ImportError", "ModuleNotFoundError", "AttributeError"}:
            return "dependency_error", child_type
        if child_type == "TimeoutError":
            return "transient", child_type
        if child_type == "ValueError":
            return "input_error", child_type
        return "runtime_error", child_type
    if isinstance(exc, (ImportError, ModuleNotFoundError, AttributeError)):
        return "dependency_error", type(exc).__name__
    if isinstance(exc, SchemaValidationError):
        return "contract_error", type(exc).__name__
    if isinstance(exc, TimeoutError):
        return "transient", type(exc).__name__
    if isinstance(exc, ValueError):
        return "input_error", type(exc).__name__
    return "runtime_error", type(exc).__name__


def traceback_hash(exc: BaseException) -> str:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return "sha256:" + hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def should_quarantine(error_class: str, *, repeated_count: int = 1, contract_threshold: int = 2) -> bool:
    if error_class == "dependency_error":
        return True
    if error_class == "contract_error" and repeated_count >= contract_threshold:
        return True
    return False
