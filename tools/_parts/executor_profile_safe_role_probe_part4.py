from __future__ import annotations

def _run_case_safe(
    root: Path, work_root: Path, row: dict[str, Any], *, project_stratum: str,
    cli_interface: str, web_interface: str, provider_interface: str,
    stateful_interface: str,
    async_interface: str,
    io_interface: str,
    framework_interface: str,
) -> dict[str, Any]:
    try:
        return _run_case(
            root, work_root, row, project_stratum=project_stratum,
            cli_interface=cli_interface, web_interface=web_interface,
            provider_interface=provider_interface,
            stateful_interface=stateful_interface,
            async_interface=async_interface,
            io_interface=io_interface,
            framework_interface=framework_interface,
        )
    except BaseException as exc:  # noqa: BLE001 - field probe preserves failures.
        return {
            "project": row.get("project"),
            "source_target": row.get("source_target"),
            "status": "needs_review",
            "executor_status": "failed",
            "profile_id": row.get("profile_id"),
            "operator_id": row.get("operator_id"),
            "score": 0.0,
            "patch_reason": "probe_exception",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "source_code_changes": False,
        }


def _discover_rows(
    projects_dir: Path, *, limit: int, max_per_project: int,
    project_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = _pathless_allowed_profiles()
    mapped = _discover_project_map_rows(
        projects_dir, allowed=allowed, limit=limit,
        max_per_project=max_per_project, project_names=project_names,
    )
    rows: list[dict[str, Any]] = list(mapped)
    seen = {str(row.get("source_target")) for row in rows}
    per_project: dict[str, int] = {}
    for row in rows:
        project = str(row.get("project") or "")
        per_project[project] = per_project.get(project, 0) + 1
    scan_roots = (
        [projects_dir / name for name in sorted(project_names) if (projects_dir / name).is_dir()]
        if project_names else [projects_dir]
    )
    for scan_root in scan_roots:
        for path in _iter_python_paths(scan_root):
            if len(rows) >= limit:
                break
            rel = path.relative_to(projects_dir).as_posix()
            if _excluded(rel, path.name):
                continue
            for row in _path_rows(projects_dir, path, allowed):
                project = str(row["project"])
                if row["source_target"] in seen or per_project.get(project, 0) >= max_per_project:
                    continue
                rows.append(row)
                seen.add(str(row["source_target"]))
                per_project[project] = per_project.get(project, 0) + 1
                if len(rows) >= limit:
                    break
    return rows


def _iter_python_paths(root: Path):
    try:
        yield from sorted(root.rglob("*.py"))
    except OSError:
        return


def _discover_project_map_rows(
    projects_dir: Path,
    *,
    allowed: set[str],
    limit: int,
    max_per_project: int,
    project_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    per_project: dict[str, int] = {}
    facade = sys.modules.get("tools.executor_profile_safe_role_probe")
    project_analyzer = getattr(facade, "analyze_project", analyze_project)
    for project_dir in sorted(path for path in projects_dir.iterdir() if path.is_dir()):
        if project_names and project_dir.name not in project_names:
            continue
        if len(rows) >= limit:
            break
        try:
            report = project_analyzer(project_dir)["project_map_report"]
        except Exception:
            continue
        capabilities = dict(dict(report.get("answers") or {}).get("3_capabilities") or {})
        for item in list(capabilities.get("pure_transforms") or [])[:120]:
            if not isinstance(item, dict):
                continue
            row = _project_map_row(project_dir.name, item, allowed)
            if not row or per_project.get(project_dir.name, 0) >= max_per_project:
                continue
            rows.append(row)
            per_project[project_dir.name] = per_project.get(project_dir.name, 0) + 1
            if len(rows) >= limit:
                break
    return rows


def _discover_domain_lineage_rows(projects_dir: Path, project_names: set[str]) -> list[dict[str, Any]]:
    rows = []
    facade = sys.modules.get("tools.executor_profile_safe_role_probe")
    project_analyzer = getattr(facade, "analyze_project", analyze_project)
    for project_name in sorted(project_names):
        project_dir = projects_dir / project_name
        if not project_dir.is_dir():
            continue
        try:
            report = project_analyzer(project_dir)["project_map_report"]
        except Exception:
            continue
        answers = dict(report.get("answers") or {})
        readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
        extraction = dict(readiness.get("minimal_extraction_plan") or {})
        ranked = list(extraction.get("capabilities_to_extract") or [])
        target = str(dict(ranked[0]).get("capability") or "") if ranked else ""
        path, separator, symbol = target.rpartition(":")
        if not separator:
            capabilities = dict(answers.get("3_capabilities") or {})
            candidates = list(capabilities.get("pure_transforms") or [])
            if not candidates:
                continue
            item = dict(candidates[0])
            path = str(item.get("path") or "")
            symbol = str(item.get("name") or "")
        if not path or not symbol:
            continue
        rows.append({
            "project": project_name,
            "source_target": f"{path}:{symbol}",
            "symbol": symbol,
            "arg": "value",
            "arg_type": "InferredInput",
            "return_type": "InferredOutput",
            "source": f"def {symbol}(value):\n    return value",
            "profile_id": "",
            "operator_id": "",
            "mutation_source": "project_map_domain_lineage_anchor",
        })
    return rows


def _project_map_row(project: str, item: dict[str, Any], allowed: set[str]) -> dict[str, Any] | None:
    args = [dict(arg) for arg in list(item.get("args") or []) if isinstance(arg, dict)]
    if len(args) != 1:
        return None
    arg = str(args[0].get("name") or "")
    symbol = str(item.get("name") or "")
    path = str(item.get("path") or "")
    if not arg or not symbol or not path:
        return None
    target = f"{path}:{symbol}"
    arg_type = str(args[0].get("annotation") or "InferredInput")
    return_type = str(item.get("returns") or "InferredOutput")
    hint = contract_profile_hint(target=target, input_contract={arg: arg_type}, output_contract={"result": return_type})
    profile = dict((hint or {}).get("contract_profile") or {})
    if str(profile.get("id") or "") not in allowed:
        return None
    return {
        "project": project,
        "source_target": target,
        "symbol": symbol,
        "arg": arg,
        "arg_type": arg_type,
        "return_type": return_type,
        "source": f"def {symbol}({arg}):\n    return {arg}",
        "profile_id": str(profile.get("id") or ""),
        "operator_id": str(profile.get("operator_id") or ""),
    }


def _path_rows(projects_dir: Path, path: Path, allowed: set[str]) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    rel = path.relative_to(projects_dir).as_posix()
    return [row for node in ast.walk(tree) if (row := _node_row(node, rel, allowed))]


def _node_row(node: ast.AST, rel: str, allowed: set[str]) -> dict[str, Any] | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.decorator_list:
        return None
    body = [item for item in node.body if not _doc_expr(item)]
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    arg = node.args.args[0].arg if len(node.args.args) == 1 else ""
    if not _single_arg_shape(node, arg):
        return None
    project, _, project_rel = rel.partition("/")
    current_operator = observed_operator(node, arg)
    identity = isinstance(body[0].value, ast.Name) and body[0].value.id == arg
    if identity and not _single_required_arg(node, arg):
        return None
    symbol = node.name
    arg_type = _annotation(node)
    return_type = _returns(node)
    if identity:
        target = f"{project_rel or rel}:{symbol}"
        hint = contract_profile_hint(
            target=target, input_contract={arg: arg_type}, output_contract={"result": return_type}
        )
        profile = dict((hint or {}).get("contract_profile") or {})
    else:
        profile_record = dict(contract_profile_for_operator(str(current_operator or "")) or {})
        symbol = str(profile_record.get("trial_symbol") or "")
        input_types = [str(item) for item in list(profile_record.get("input_types") or []) if item]
        output_types = [str(item) for item in list(profile_record.get("output_types") or []) if item]
        arg_type = input_types[0] if input_types else "InferredInput"
        return_type = output_types[0] if output_types else "InferredOutput"
        profile = {
            "id": profile_record.get("id"),
            "operator_id": profile_record.get("operator_id"),
        }
        target = f"{project_rel or rel}:{symbol}"
    profile_id = str(profile.get("id") or "")
    if not symbol or not profile_id:
        return None
    if identity and profile_id not in allowed:
        return None
    if not identity and current_operator != str(profile.get("operator_id") or ""):
        return None
    source = (
        ast.unparse(ast.fix_missing_locations(_clean_function(node)))
        if identity else identity_mutation_source(node, arg, function_name=symbol)
    )
    return {
        "project": project,
        "source_target": target,
        "symbol": symbol,
        "arg": arg,
        "arg_type": arg_type,
        "return_type": return_type,
        "source": source,
        "profile_id": profile_id,
        "operator_id": str(profile.get("operator_id") or ""),
        "mutation_source": "existing_identity" if identity else "real_operator_replaced_with_identity",
        "oracle_operator_id": current_operator,
    }

