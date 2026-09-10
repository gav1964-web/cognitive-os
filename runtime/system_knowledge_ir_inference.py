"""Surface-based fallback contracts for SystemKnowledgeIR."""

from __future__ import annotations

from typing import Any


def inferred_behavior_contract(interface: dict[str, Any], domain_model: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = str(interface.get("kind") or "interface")
    name = str(interface.get("name") or "")
    domain = dict(domain_model or {})
    profile = dict(domain.get("domain_profile") or {})
    domain_kind = str(profile.get("kind") or domain.get("project_type") or "generic")
    inputs = _list(profile.get("input_summary"))
    outputs = _list(profile.get("output_summary"))
    scenarios = _list(profile.get("scenario_summary"))
    if kind == "route":
        return {
            "source": name,
            "contract_family": _family("http_surface", domain_kind),
            "input_contract": {"request": inputs or "HTTP request matching route and method"},
            "output_contract": {"response": outputs or "documented or observed response shape"},
            "scenario_contract": scenarios[:4],
            "failure_contract": _failure_contract(kind, domain_kind),
            "evidence": "inferred_from_project_surface",
        }
    return {
        "source": name,
        "contract_family": _family("entrypoint_surface", domain_kind),
        "input_contract": {"call": inputs or "import or execute public entrypoint"},
        "output_contract": {"result": outputs or "documented behavior or available module surface"},
        "scenario_contract": scenarios[:4],
        "failure_contract": _failure_contract(kind, domain_kind),
        "evidence": "inferred_from_project_surface",
    }


def inferred_acceptance(interface: dict[str, Any]) -> dict[str, Any]:
    kind = str(interface.get("kind") or "interface")
    name = str(interface.get("name") or "")
    return {
        "id": f"surface_{kind}_{_slug(name)}",
        "criterion": f"Generated project preserves public {kind} `{name}` as recoverable source evidence.",
        "source": "SystemKnowledgeIR.public_interfaces",
        "evidence": "inferred_from_project_surface",
    }


def _slug(value: str) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in value)
    parts = [part for part in text.split("_") if part]
    return "_".join(parts)[-80:] or "unknown"


def _family(surface: str, domain_kind: str) -> str:
    normalized = _slug(domain_kind)
    return f"inferred_{normalized}_{surface}" if normalized != "generic" else f"inferred_{surface}"


def _failure_contract(kind: str, domain_kind: str) -> list[str]:
    failures = ["invalid input is explicit", "dependency/runtime failure is reported without hidden mutation"]
    domain = domain_kind.lower()
    if "server" in domain or kind == "route":
        failures.append("timeout, disconnect, or malformed request returns a controlled response")
    if "compute" in domain or "array" in domain:
        failures.append("shape, dtype, missing-value, or tolerance errors are explicit")
    if "template" in domain:
        failures.append("missing template, invalid context, and escaping failures are explicit")
    return failures


def _list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []
