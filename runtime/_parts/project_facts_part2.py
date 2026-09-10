from __future__ import annotations

from typing import Any


def _subsystems(
    summary: dict[str, Any],
    routes: list[dict[str, Any]],
    central_nodes: list[dict[str, Any]],
    broad_nodes: list[dict[str, Any]],
    weak_contracts: list[str],
    import_hubs: list[dict[str, Any]],
    test_surface: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in list(summary.get("read_files", []) or []) + list(summary.get("entrypoints", []) or []):
        _touch_subsystem(rows, _subsystem_name(str(path)), "file")
    for route in routes:
        name = _subsystem_name(str(route.get("path") or ""))
        _touch_subsystem(rows, name, "route")
    for node in central_nodes:
        name = _subsystem_name(str(node.get("path") or ""))
        _touch_subsystem(rows, name, "central")
    for node in broad_nodes:
        name = _subsystem_name(str(node.get("path") or ""))
        _touch_subsystem(rows, name, "broad")
    for item in weak_contracts:
        name = _subsystem_name(str(item).split(":", 1)[0])
        _touch_subsystem(rows, name, "weak_contract")
    for hub in import_hubs:
        name = _subsystem_name(str(hub.get("path") or ""))
        _touch_subsystem(rows, name, "import_hub")
    for row in rows.values():
        row["score"] = row["routes"] * 3 + row["central"] * 3 + row["broad"] * 4 + row["weak_contracts"] * 2 + row["import_hubs"] * 2 + row["files"]
        row["test_files_seen"] = test_surface.get("test_files_seen", test_surface.get("test_files", 0))
    return sorted(rows.values(), key=lambda item: (-item["score"], item["name"]))[:8]

def _touch_subsystem(rows: dict[str, dict[str, Any]], name: str, kind: str) -> None:
    if not name:
        return
    row = rows.setdefault(
        name,
        {"name": name, "files": 0, "routes": 0, "central": 0, "broad": 0, "weak_contracts": 0, "import_hubs": 0},
    )
    if kind == "file":
        row["files"] += 1
    elif kind == "route":
        row["routes"] += 1
    elif kind == "central":
        row["central"] += 1
    elif kind == "broad":
        row["broad"] += 1
    elif kind == "weak_contract":
        row["weak_contracts"] += 1
    elif kind == "import_hub":
        row["import_hubs"] += 1

def _architectural_hotspots(
    central_nodes: list[dict[str, Any]],
    broad_nodes: list[dict[str, Any]],
    weak_contracts: list[str],
    import_hubs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hotspots = []
    for node in broad_nodes[:5]:
        hotspots.append({"kind": "broad_function", "target": _node_ref(node), "weight": node.get("loc") or node.get("call_count") or 1})
    for node in central_nodes[:5]:
        hotspots.append({"kind": "central_flow", "target": _node_ref(node), "weight": node.get("call_count") or node.get("loc") or 1})
    for contract in weak_contracts[:6]:
        hotspots.append({"kind": "weak_contract", "target": contract, "weight": 2})
    for hub in import_hubs[:5]:
        hotspots.append({"kind": "import_hub", "target": hub.get("path"), "weight": hub.get("internal_import_count") or 1})
    return sorted(hotspots, key=lambda item: (-int(item.get("weight") or 0), str(item.get("target"))))[:10]

def _ownership_boundaries(
    summary: dict[str, Any],
    routes: list[dict[str, Any]],
    import_hubs: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    boundaries = []
    entrypoints = summary.get("entrypoints", []) or []
    if len(entrypoints) > 1:
        boundaries.append({"kind": "multiple_entrypoints", "target": ", ".join(str(item) for item in entrypoints[:4])})
    route_subsystems = sorted({_subsystem_name(str(route.get("path") or "")) for route in routes if route.get("path")})
    if len(route_subsystems) > 1:
        boundaries.append({"kind": "routes_cross_subsystems", "target": ", ".join(route_subsystems[:5])})
    for hub in import_hubs[:3]:
        boundaries.append({"kind": "import_hub_boundary", "target": str(hub.get("path"))})
    if any(risk.get("code") == "packaged_copy_detected" for risk in risks):
        boundaries.append({"kind": "packaged_copy", "target": "map_install_package"})
    return boundaries[:8]

def _subsystem_name(path: str) -> str:
    clean = path.replace("\\", "/").strip("/")
    if not clean:
        return ""
    parts = clean.split("/")
    if parts[0] in {"app", "src", "p0048"} and len(parts) > 1:
        return "/".join(parts[:2])
    if parts[0] in {"tests", "tools", "plugins"} and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]

def _node_ref(node: dict[str, Any]) -> str:
    path = node.get("path")
    name = node.get("name")
    return f"{path}:{name}" if name else str(path)
