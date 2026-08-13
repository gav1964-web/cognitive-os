"""Question-oriented project analysis answers."""

from __future__ import annotations

from typing import Any

from .core_paths import is_core_path
from .doc_purpose import descriptive_purpose_heading, docs_text, purpose_heading, purpose_sentence
from .domain_profile import infer_domain_profile
from .error_model_answers import (
    error_handling_hints,
    likely_error_types,
    minimal_loop,
    reproducibility,
    state_to_preserve,
)
from .execution_contract_answers import (
    artifacts_to_persist,
    auto_contract_feasibility,
    capability_candidates,
    command_summary,
    data_structures,
    execution_path,
    fallback_logic,
    pipeline_candidate,
    looks_like_python_library,
    weak_contract_zones,
)
from .runtime_readiness import (
    best_effort_dataflows,
    contract_test_strategy,
    data_lifecycle,
    evidence_claims,
    hidden_orchestrators,
    idempotency_risks,
    long_lived_state,
    minimal_extraction_plan,
    mixed_responsibility_functions,
    process_boundary_candidates,
    quarantine_candidates,
    resume_reuse_plan,
    source_strata,
)


def build_answers(
    summary: dict[str, Any],
    risks: list[dict[str, str]],
    stack: dict[str, Any],
    files: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
) -> dict[str, Any]:
    routes = python_structure.get("routes", [])
    commands = _active_commands(runtime_commands.get("commands", []))
    imports = set(python_structure.get("imports", []))
    insights = dict(python_structure.get("project_insights", {}))
    docs = docs_text(files)
    project_type = _project_type(summary, imports)
    domain_profile = infer_domain_profile(summary, files, python_structure, routes, imports)
    return {
        "1_scope": {
            "main_task": _main_task(project_type, summary, docs, domain_profile),
            "supported_scenarios": _scenarios(summary, routes, commands, imports, domain_profile, python_structure),
            "inputs": _inputs(routes, commands, imports, domain_profile, python_structure),
            "outputs": _outputs(routes, commands, imports, stack, domain_profile, python_structure),
            "code_areas": _code_areas(python_structure),
            "test_surface": insights.get("test_surface", {}),
            "domain_profile": domain_profile,
        },
        "2_execution": {
            "entrypoints": summary.get("entrypoints", []),
            "runtime_commands": [command_summary(command) for command in commands[:10]],
            "primary_execution_path": execution_path(summary, routes, commands, domain_profile),
            "central_flow_nodes": _active_nodes(python_structure.get("central_nodes", []))[:8],
            "implicit_orchestration": _active_nodes(python_structure.get("wide_functions", []))[:8],
            "internal_import_hubs": _active_nodes(insights.get("import_graph", []))[:8],
            "pipeline_candidate": pipeline_candidate(summary, routes, commands),
        },
        "3_capabilities": {
            "atomic_reusable_capabilities": capability_candidates(python_structure, routes, commands),
            "pure_transforms": _core_pure_transforms(python_structure),
            "too_broad_functions": _active_nodes(python_structure.get("wide_functions", []))[:8],
            "environment_dependencies": python_structure.get("external_dependencies", {}),
            "fallback_logic": fallback_logic(python_structure, docs),
        },
        "4_contracts_data": {
            "main_data_structures": data_structures(python_structure),
            "explicit_schemas": dict(python_structure.get("contracts", {})).get("schema_like_classes", []),
            "schema_fields": insights.get("schema_fields", [])[:8],
            "weak_contract_zones": weak_contract_zones(python_structure),
            "artifacts_to_persist": artifacts_to_persist(imports, stack),
            "auto_contract_feasibility": auto_contract_feasibility(python_structure),
        },
        "5_errors_state_repro": {
            "likely_error_types": likely_error_types(risks, imports),
            "explicit_error_handling": error_handling_hints(python_structure),
            "error_details": insights.get("error_handling", {}),
            "state_to_preserve": state_to_preserve(imports, stack),
            "reproducibility": reproducibility(files, stack, commands),
            "minimal_cognitive_loop": minimal_loop(routes, commands),
        },
        "6_runtime_extraction_readiness": {
            "data_lifecycle": data_lifecycle(project_type, routes, commands, python_structure),
            "dataflows": best_effort_dataflows(python_structure),
            "evidence_claims": evidence_claims(python_structure),
            "mixed_responsibility_functions": mixed_responsibility_functions(python_structure),
            "hidden_orchestrators": hidden_orchestrators(python_structure),
            "long_lived_state": long_lived_state(imports, stack, python_structure),
            "idempotency_risks": idempotency_risks(python_structure),
            "quarantine_candidates": quarantine_candidates(risks, imports, python_structure),
            "process_boundary_candidates": process_boundary_candidates(python_structure),
            "contract_test_strategy": contract_test_strategy(python_structure),
            "resume_reuse_plan": resume_reuse_plan(routes, commands, imports),
            "minimal_extraction_plan": minimal_extraction_plan(python_structure, routes, commands),
            "source_strata": source_strata(python_structure),
        },
    }


def _active_commands(commands: Any) -> list[dict[str, Any]]:
    if not isinstance(commands, list):
        return []
    return [
        command
        for command in commands
        if isinstance(command, dict) and is_core_path(str(command.get("path", "")))
    ]


def _active_nodes(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict) and is_core_path(str(row.get("path", "")))
    ]


def inline_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "none"
        return "; ".join(inline_value(item) for item in value[:8])
    if isinstance(value, dict):
        return "; ".join(f"{key}={inline_value(val)}" for key, val in list(value.items())[:8])
    return str(value)


def _project_type(summary: dict[str, Any], imports: set[str]) -> str:
    frameworks = set(summary.get("frameworks", []))
    if "FastAPI" in frameworks:
        return "FastAPI API service"
    if "Flask-like Python web app" in frameworks:
        return "Flask web application"
    if "sqlite3" in imports or summary.get("entrypoints"):
        return "Python automation/tooling project"
    return "Python project"


def _main_task(project_type: str, summary: dict[str, Any], docs: str, domain_profile: dict[str, Any] | None = None) -> str:
    profile = dict(domain_profile or {})
    if profile.get("purpose_summary"):
        return str(profile["purpose_summary"])
    if profile.get("kind") == "llm_provider_gateway":
        return "Provide a unified OpenAI-compatible gateway for routing chat/completion requests across multiple LLM providers."
    if profile.get("kind") == "llm_auto_repair_loop":
        return "Run an LLM-assisted auto-repair loop: copy a template workspace, build/run it in Docker, send failures to an LLM, apply proposed file updates, and retry."
    if profile.get("kind") == "ml_competition_inference_script":
        return "Run an ML competition inference workflow: load prompt/test CSV rows, generate model answers, postprocess them, and write a submission-style CSV."
    if docs:
        descriptive_heading = descriptive_purpose_heading(docs)
        if descriptive_heading:
            return f"Inferred from docs: {descriptive_heading} ({project_type})."
        sentence = purpose_sentence(docs)
        if sentence:
            return f"Inferred from docs: {sentence} ({project_type})."
        heading = purpose_heading(docs)
        if heading:
            return f"Inferred from docs: {heading} ({project_type})."
    if project_type == "FastAPI API service":
        return "Expose an HTTP API service and return structured JSON responses."
    if project_type == "Flask web application":
        return "Serve a web application with HTTP endpoints and browser-facing data/API responses."
    entrypoints = ", ".join(summary.get("entrypoints", [])[:3])
    return f"Run project-specific Python workflows through detected entrypoints ({entrypoints})."


def _scenarios(
    summary: dict[str, Any],
    routes: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    imports: set[str] | None = None,
    domain_profile: dict[str, Any] | None = None,
    python_structure: dict[str, Any] | None = None,
) -> list[str]:
    profile = dict(domain_profile or {})
    imports = imports or set()
    if profile.get("scenario_summary"):
        return [str(item) for item in profile.get("scenario_summary", []) if item][:5]
    scenarios = []
    route_names = {route.get("route") for route in routes}
    if profile.get("kind") == "llm_provider_gateway":
        scenarios.extend(
            [
                "Accept OpenAI-compatible chat/completion requests.",
                "Route requests to configured LLM providers and model profiles.",
                "Normalize provider responses and errors into gateway API responses.",
            ]
        )
    if profile.get("kind") == "llm_auto_repair_loop":
        scenarios.extend(
            [
                "Copy a template project into a disposable workspace.",
                "Build and run the workspace through Docker Compose.",
                "Send build/runtime failures plus project files to an LLM for repair suggestions.",
                "Apply returned file updates and retry until success or attempt budget is exhausted.",
                "Persist successful workspace files back into the template.",
            ]
        )
    if profile.get("kind") == "ml_competition_inference_script":
        scenarios.extend(
            [
                "Load prompt/test rows from CSV data files.",
                "Load tokenizer/model artifacts or external model dependencies.",
                "Generate answers for each row and postprocess model output.",
                "Write a submission-style CSV with generated answers.",
            ]
        )
    if _looks_like_command_handler(python_structure):
        scenarios.extend(
            [
                "Parse user text commands into command name and payload.",
                "Dispatch recognized commands to handler functions.",
                "Preserve per-user/session state and return user-facing text responses.",
            ]
        )
    if routes:
        scenarios.append(f"Serve HTTP API/web requests across {len(routes)} detected routes.")
    if any(command.get("purpose") == "install_dependencies" for command in commands):
        scenarios.append("Install project dependencies from runtime scripts.")
    if any(command.get("purpose") == "run_application" for command in commands):
        scenarios.append("Start the application from a local runtime script.")
    if summary.get("entrypoints") and imports & {"json", "csv", "openpyxl", "zipfile"}:
        scenarios.append("Process user-provided files or structured documents through the detected entrypoint.")
        scenarios.append("Write serialized output artifacts or filesystem results for downstream inspection.")
    if any(command.get("purpose") == "rebuild_data" for command in commands):
        scenarios.append("Rebuild derived data artifacts from scripts.")
    if "/v1/chat/completions" in route_names or "/chat" in route_names:
        scenarios.append("Handle chat/completion API requests.")
    if not scenarios and looks_like_python_library(summary):
        scenarios.extend(
            [
                "Import package modules and call public library APIs from user code.",
                "Transform caller-provided Python objects into library results or side effects.",
                "Handle domain-specific errors at package/API boundaries.",
            ]
        )
    if not scenarios and summary.get("entrypoints"):
        scenarios.append("Run CLI/tooling entrypoints detected in the project tree.")
    return scenarios[:5]


def _inputs(
    routes: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    imports: set[str],
    domain_profile: dict[str, Any] | None = None,
    python_structure: dict[str, Any] | None = None,
) -> list[str]:
    profile = dict(domain_profile or {})
    if profile.get("input_summary"):
        return [str(item) for item in profile.get("input_summary", []) if item][:8]
    inputs = []
    if profile.get("kind") == "llm_provider_gateway":
        inputs.extend(["OpenAI-compatible chat/completion requests", "provider/model routing configuration"])
    if profile.get("kind") == "llm_auto_repair_loop":
        inputs.extend(["template source files", "Docker build/run logs", "LLM repair JSON"])
    if profile.get("kind") == "ml_competition_inference_script":
        inputs.extend(["prompt/test CSV rows", "model/tokenizer configuration", "large model/index artifacts"])
    if routes:
        inputs.append("HTTP requests")
    if commands:
        inputs.append("CLI/script invocation")
    if imports & {"json", "csv", "openpyxl", "zipfile"}:
        inputs.append("files or structured documents")
    if imports & {"requests", "httpx", "openai"}:
        inputs.append("external API responses")
    if _looks_like_command_handler(python_structure):
        inputs.extend(["user id/session key", "text command payload"])
    return inputs or ["not enough evidence"]


def _outputs(
    routes: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    imports: set[str],
    stack: dict[str, Any],
    domain_profile: dict[str, Any] | None = None,
    python_structure: dict[str, Any] | None = None,
) -> list[str]:
    profile = dict(domain_profile or {})
    if profile.get("output_summary"):
        return [str(item) for item in profile.get("output_summary", []) if item][:8]
    outputs = []
    if profile.get("kind") == "llm_provider_gateway":
        outputs.extend(["OpenAI-compatible chat/completion responses", "normalized provider error responses"])
    if profile.get("kind") == "llm_auto_repair_loop":
        outputs.extend(["updated workspace/template files", "Docker build/run status", "repair attempt history"])
    if profile.get("kind") == "ml_competition_inference_script":
        outputs.extend(["submission CSV rows", "generated answer text", "runtime/model failure evidence"])
    if routes:
        outputs.append("HTTP/API responses")
    if imports & {"json", "csv", "openpyxl", "zipfile"}:
        outputs.append("files or serialized artifacts")
    if imports & {"sqlite3", "sqlalchemy"}:
        outputs.append("database state")
    if commands or stack.get("large_artifacts"):
        outputs.append("side effects in local filesystem")
    if _looks_like_command_handler(python_structure):
        outputs.extend(["user-facing text response", "updated in-memory session state"])
    return outputs or ["not enough evidence"]


def _looks_like_command_handler(python_structure: dict[str, Any] | None) -> bool:
    names = _function_names(python_structure or {})
    return (
        any(name in names for name in ("parse_command", "parse_message", "parse_update"))
        and any(name in names for name in ("dispatch", "dispatch_command", "handle_message"))
        and any(name.startswith("handle_") for name in names)
    )


def _function_names(python_structure: dict[str, Any]) -> set[str]:
    names = set()
    for file_row in list(python_structure.get("files") or []):
        if not isinstance(file_row, dict):
            continue
        for function in list(file_row.get("functions") or []):
            if isinstance(function, dict) and function.get("name"):
                names.add(str(function["name"]))
    for key in ("central_nodes", "wide_functions", "pure_transform_candidates"):
        for function in list(python_structure.get(key) or []):
            if isinstance(function, dict) and function.get("name"):
                names.add(str(function["name"]))
    return names


def _code_areas(python_structure: dict[str, Any]) -> dict[str, list[str]]:
    paths = [str(item.get("path", "")) for item in python_structure.get("files", [])]
    active = [path for path in paths if is_core_path(path)]
    return {
        "core_logic": active[:10],
        "interfaces_adapters": [
            path
            for path in active
            if any(part in path.lower() for part in ("api", "server", "client", "adapter", "app.py"))
        ][:10],
        "tests": [path for path in paths if path.startswith("tests/") or "/test" in path][:10],
        "experiments_tools": [path for path in paths if path.startswith(("tools/", "scratch/", "examples/"))][:10],
    }


def _core_pure_transforms(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in python_structure.get("pure_transform_candidates", [])
        if is_core_path(str(item.get("path", "")))
    ][:12]
