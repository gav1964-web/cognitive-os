from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class _Check:
    code: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": "failed" if self.errors else "passed",
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _load_check(code: str, fn: Callable[[], Any]) -> _Check:
    check = _Check(code)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - doctor reports config failures.
        check.errors.append(f"{type(exc).__name__}:{exc}")
    return check
