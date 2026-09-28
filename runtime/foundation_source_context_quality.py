"""Project-size-aware source context quality checks."""

from __future__ import annotations

from typing import Any

from runtime.python_source_files import is_python_source_ref


def source_context_is_sufficient(
    project: dict[str, Any], adr: dict[str, Any], *, minimum_refs: int
) -> bool:
    summary = dict(project.get("summary") or {})
    python_files = {
        str(item) for item in list(summary.get("read_files") or []) if is_python_source_ref(str(item))
    }
    required = min(minimum_refs, max(1, len(python_files)))
    source_context = dict(adr.get("source_context") or {})
    source_refs = [key for key in source_context if is_python_source_ref(str(key))]
    return len(source_refs) >= required
