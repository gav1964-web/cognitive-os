from __future__ import annotations

def _benchmark_archetype(project_stratum: str) -> str:
    return {
        "cli_local_tool": "derived_cli_mutation_benchmark",
        "web_api_middleware": "derived_http_mutation_benchmark",
        "sdk_provider_integration": "derived_provider_adapter_mutation_benchmark",
        "stateful_service_database": "derived_sqlite_state_mutation_benchmark",
        "async_worker_scheduler": "derived_async_execution_mutation_benchmark",
        "external_process_io": "derived_external_io_mutation_benchmark",
        "framework_plugin_build": "derived_framework_artifact_mutation_benchmark",
        "data_tabular_pipeline": "derived_tabular_transform_benchmark",
        "scientific_compute": "derived_scientific_transform_benchmark",
        "ml_inference": "derived_inference_transform_benchmark",
        "ml_training_checkpoint": "derived_training_transform_benchmark",
        "llm_multi_agent": "derived_llm_contract_mutation_benchmark",
    }.get(project_stratum, "derived_mutation_benchmark")


DOMAIN_BENCHMARK_RECIPES = {
    "data_tabular_pipeline": [
        ("drop_missing_fields", "present_mapping", "drop_none_values", "mapping", "mapping"),
        ("sort_numeric_values", "sorted_list", "sorted_list", "list[number]", "list[number]"),
        ("deduplicate_rows", "unique_list", "unique_preserve_order", "list", "list"),
    ],
    "scientific_compute": [
        ("center_numeric_values", "mean_center_values", "mean_center_values", "list[number]", "list[number]"),
        ("square_numeric_values", "square_values", "square_values", "list[number]", "list[number]"),
        ("normalize_numeric_range", "minmax_scale_values", "minmax_scale_values", "list[number]", "list[number]"),
    ],
    "ml_inference": [
        ("threshold_predictions", "threshold_binary", "threshold_binary", "list[number]", "list[int]"),
        ("best_prediction_index", "argmax_index", "argmax_index", "list[number]", "int"),
        ("bound_probabilities", "clamp_probabilities", "clamp_probabilities", "list[number]", "list[number]"),
    ],
    "ml_training_checkpoint": [
        ("clip_gradients", "clip_signed_unit", "clip_signed_unit", "list[number]", "list[number]"),
        ("decay_learning_rate", "decay_rate", "decay_rate", "number", "number"),
        ("discount_returns", "discount_returns", "discount_returns", "list[number]", "list[number]"),
    ],
    "llm_multi_agent": [
        ("normalize_message_role", "normalize_string", "strip_lower", "string", "string"),
        ("deduplicate_tool_names", "unique_list", "unique_preserve_order", "list", "list"),
        ("drop_missing_response_fields", "present_mapping", "drop_none_values", "mapping", "mapping"),
    ],
}


def _domain_benchmark_rows(rows: list[dict[str, Any]], project_stratum: str) -> list[dict[str, Any]]:
    recipes = DOMAIN_BENCHMARK_RECIPES.get(project_stratum)
    if not recipes:
        return rows
    transformed = []
    by_project: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_project.setdefault(str(row.get("project") or ""), []).append(row)
    for project_rows in by_project.values():
        for index, (symbol, profile_id, operator_id, arg_type, return_type) in enumerate(recipes):
            row = project_rows[index % len(project_rows)]
            arg = "values" if "list" in arg_type else "value"
            transformed.append({
                **row,
                "symbol": symbol,
                "arg": arg,
                "arg_type": arg_type,
                "return_type": return_type,
                "source": f"def {symbol}({arg}):\n    return {arg}",
                "profile_id": profile_id,
                "operator_id": operator_id,
                "mutation_source": "domain_contract_identity_benchmark",
            })
    return transformed


def _adr(target: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": f"Implement verified {row['operator_id']} transform in the profile-safe role chain",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare profile-safe transform."],
            "files_or_symbols": [target],
            "requested_contract_profile": {
                "id": row["profile_id"],
                "operator_id": row["operator_id"],
                "evidence": row["source_target"],
            },
        },
        "traceability": [{"source": target, "requirement": "Capability candidate requires TechnicalSpec."}],
        "source_context": {
            target: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": row["arg"], "annotation": row["arg_type"]}], "returns": row["return_type"]},
                "snippet": {"text": row["source"]},
            }
        },
    }


def _pathless_allowed_profiles() -> set[str]:
    policy = dict(load_architecture_decision_policy().get("source_selection") or {})
    fallback = dict(policy.get("callable_transform_fallback") or {})
    return {str(item) for item in list(fallback.get("pathless_allowed_contract_profiles") or [])}


def _single_required_arg(node: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> bool:
    args = node.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
        return False
    return len(args.args) == 1 and args.args[0].arg == arg and not args.defaults


def _single_arg_shape(node: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> bool:
    args = node.args
    return bool(
        arg and not args.vararg and not args.kwarg and not args.kwonlyargs
        and not args.posonlyargs and len(args.args) == 1 and args.args[0].arg == arg
    )


def _clean_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    clone = ast.parse(ast.unparse(node)).body[0]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef))
    clone.decorator_list = []
    clone.returns = None
    clone.args.args[0].annotation = None
    return clone


def _annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    annotation = node.args.args[0].annotation if node.args.args else None
    return ast.unparse(annotation) if annotation is not None else "InferredInput"


def _returns(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    return ast.unparse(node.returns) if node.returns is not None else "InferredOutput"


def _doc_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _excluded(rel: str, name: str) -> bool:
    low = "/" + rel.lower()
    tokens = ("/tests/", "/test/", "/testing/", "/scripts/", "/examples/", "/migrations/", "/docs/")
    return name.startswith("test_") or name.endswith("_test.py") or any(token in low for token in tokens)


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}_{_stamp()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _read_json(path: Any) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    except Exception:
        return {}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
