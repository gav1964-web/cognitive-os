from __future__ import annotations
from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill
def _run_spec_writer(architecture_decision: dict):
    return run_role_skill(producer_for_artifact_type("TechnicalSpec"), architecture_decision=architecture_decision)

def test_spec_writer_demotes_constructor_logging_and_generic_predicate_targets():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate low-value first-slice target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/worker/base.py:__init__",
                "pkg/__init__.py:configure_logging",
                "pkg/queries.py:all",
                "pkg/providers/factory.py:build_providers_from_config",
            ],
        },
        "traceability": [
            {"source": "pkg/worker/base.py:__init__", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/__init__.py:configure_logging", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/queries.py:all", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "pkg/providers/factory.py:build_providers_from_config",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "pkg/worker/base.py:__init__": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "self", "annotation": "Any"}], "returns": "None"},
                "snippet": {"text": "def __init__(self): ..."},
            },
            "pkg/__init__.py:configure_logging": {
                "kind": "central_flow_node",
                "signature": {"args": [], "returns": "None"},
                "snippet": {"text": "def configure_logging(): ..."},
            },
            "pkg/queries.py:all": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "items", "annotation": "list"}], "returns": "bool"},
                "snippet": {"text": "def all(items): ..."},
            },
            "pkg/providers/factory.py:build_providers_from_config": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "config", "annotation": "dict"}], "returns": "list[Provider]"},
                "snippet": {"text": "def build_providers_from_config(config): ..."},
                "callers": ["pkg/api.py:create_app"],
                "central_flow_node": {"call_count": 6},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/providers/factory.py:build_providers_from_config"
    assert spec["extraction_contract"]["semantic_quality"]["status"] == "strong"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    low_value_reasons = " ".join(ranked["pkg/worker/base.py:__init__"]["reasons"])
    assert "constructor/logging/config helper" in low_value_reasons


def test_spec_writer_keeps_selected_candidate_in_interface_contracts_when_many_targets():
    sources = [f"pkg/mod.py:helper_{index}" for index in range(20)]
    selected = "pkg/core.py:parse_payload"
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Keep selected candidate handoff contract visible",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [*sources, selected],
            "contract_targets": [{"source": source} for source in [*sources, selected]],
        },
        "traceability": [
            {"source": source, "requirement": "Capability candidate requires TechnicalSpec."}
            for source in [*sources, selected]
        ],
        "source_context": {
            **{
                source: {
                    "kind": "unknown",
                    "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "dict"},
                    "snippet": {"text": "def helper(payload): ..."},
                }
                for source in sources
            },
            selected: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "ParsedPayload"},
                "snippet": {"text": "def parse_payload(payload): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == selected
    assert spec["interface_contracts"][0]["source"] == selected


def test_spec_writer_demotes_liveness_probe_when_domain_target_exists():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Avoid health endpoint as first contract",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["api.py:health", "api.py:list_provider_capabilities"],
        },
        "traceability": [
            {"source": "api.py:health", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "api.py:list_provider_capabilities", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "api.py:health": {
                "kind": "unknown",
                "signature": {"args": [], "returns": "dict"},
                "snippet": {"text": "def health(): return {'ok': True}"},
            },
            "api.py:list_provider_capabilities": {
                "kind": "unknown",
                "signature": {"args": [], "returns": "list[ProviderCapability]"},
                "snippet": {"text": "def list_provider_capabilities(): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "api.py:list_provider_capabilities"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "health/status/ping probe" in " ".join(ranked["api.py:health"]["reasons"])


def test_spec_writer_prefers_read_query_contract_over_write_operation():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate mutation target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["tinydb/storages.py:write", "tinydb/table.py:search"],
        },
        "traceability": [
            {"source": "tinydb/storages.py:write", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "tinydb/table.py:search", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "tinydb/storages.py:write": {
                "kind": "unknown",
                "signature": {"args": [{"name": "data", "annotation": "dict"}], "returns": "None"},
                "snippet": {"text": "def write(data): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
            "tinydb/table.py:search": {
                "kind": "unknown",
                "signature": {"args": [{"name": "cond", "annotation": "QueryLike"}], "returns": "list[Document]"},
                "snippet": {"text": "def search(cond): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "tinydb/table.py:search"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    write_reasons = " ".join(ranked["tinydb/storages.py:write"]["reasons"])
    assert "write/update/delete operation" in write_reasons


def test_spec_writer_promotes_stronger_domain_candidate_over_cli_support_helper():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer project-domain template resolution over support listing helper",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "cli.py:list_installed_templates",
                "find.py:find_template",
            ],
        },
        "traceability": [
            {"source": "cli.py:list_installed_templates", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "find.py:find_template", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "cli.py:list_installed_templates": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "directory", "annotation": "Path"}], "returns": "list[str]"},
                "snippet": {"text": "def list_installed_templates(directory): ..."},
                "callers": ["cli.py:main"],
            },
            "find.py:find_template": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "repo_dir", "annotation": "Path"}], "returns": "Path"},
                "snippet": {"text": "def find_template(repo_dir): ..."},
                "callers": ["main.py:cookiecutter"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "find.py:find_template"
    assert spec["extraction_contract"]["semantic_quality"]["status"] == "strong"


def test_spec_writer_prefers_product_domain_core_over_release_support_surface():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer crypto product surface over release automation",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "crypto_hash_contract_slice",
            "targets": ["release.py:release", "src/bcrypt/_bcrypt.py:hashpw"],
            "steps": ["Define password bytes input.", "Verify salt/hash output."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["release.py:release", "src/bcrypt/_bcrypt.py:hashpw"],
        },
        "traceability": [
            {"source": "release.py:release", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "src/bcrypt/_bcrypt.py:hashpw", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "release.py:release": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "version", "annotation": "str"}], "returns": "None"},
                "snippet": {"text": "def release(version): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
            "src/bcrypt/_bcrypt.py:hashpw": {
                "kind": "pure_transform",
                "signature": {
                    "args": [
                        {"name": "password", "annotation": "bytes"},
                        {"name": "salt", "annotation": "bytes"},
                    ],
                    "returns": "bytes",
                },
                "snippet": {"text": "def hashpw(password, salt): ..."},
                "candidate_level": "helper_transform",
                "candidate_score": 70,
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "src/bcrypt/_bcrypt.py:hashpw"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "release/build/publish support surface" in " ".join(ranked["release.py:release"]["reasons"])


def test_spec_writer_does_not_promote_weak_first_slice_over_strong_core_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Avoid weak first-slice override",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "request_boundary_slice",
            "targets": ["app/api/handlers.py:handle_chat(186 loc)", "app/providers/factory.py:build_providers_from_config"],
            "steps": ["Define request envelope.", "Keep provider selection pure."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "app/api/handlers.py:handle_chat",
                "app/providers/factory.py:build_providers_from_config",
            ],
        },
        "traceability": [
            {"source": "app/api/handlers.py:handle_chat", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "app/providers/factory.py:build_providers_from_config",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "app/api/handlers.py:handle_chat": {
                "kind": "broad_function",
                "signature": {
                    "args": [{"name": "request", "annotation": "LegacyChatRequest"}],
                    "returns": "",
                },
                "snippet": {"text": "def handle_chat(request): ..."},
                "side_effects": ["database"],
            },
            "app/providers/factory.py:build_providers_from_config": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "app_config", "annotation": "AppConfig"}], "returns": "dict[str, Provider]"},
                "snippet": {"text": "def build_providers_from_config(app_config): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "app/providers/factory.py:build_providers_from_config"
    assert spec["extraction_contract"]["input_contract"] == {"app_config": "AppConfig"}
    assert spec["extraction_contract"]["output_contract"] == {"result": "dict[str, Provider]"}


def test_spec_writer_first_slice_scope_chooses_best_candidate_inside_slice():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Choose the best candidate within the architect first slice",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "source_parse_analyze_report_slice",
            "targets": [
                "src/flake8/options/parse_args.py:parse_args(56 loc)",
                "src/flake8/main/options.py:register_default_options(288 loc)",
            ],
            "steps": ["Define command options.", "Register default options."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "src/flake8/options/parse_args.py:parse_args",
                "src/flake8/main/options.py:register_default_options",
                "src/flake8/plugins/pycodestyle.py:pycodestyle_logical",
            ],
        },
        "traceability": [
            {
                "source": "src/flake8/options/parse_args.py:parse_args",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
            {
                "source": "src/flake8/main/options.py:register_default_options",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "src/flake8/options/parse_args.py:parse_args": {
                "kind": "unknown",
                "signature": {"args": [{"name": "argv", "annotation": "list[str]"}], "returns": "Namespace"},
                "snippet": {"text": "def parse_args(argv): ..."},
            },
            "src/flake8/main/options.py:register_default_options": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "parser", "annotation": "OptionManager"}], "returns": "None"},
                "snippet": {"text": "def register_default_options(parser): ..."},
            },
            "src/flake8/plugins/pycodestyle.py:pycodestyle_logical": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "physical_line", "annotation": "str"}], "returns": "Generator"},
                "snippet": {"text": "def pycodestyle_logical(physical_line): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "src/flake8/main/options.py:register_default_options"
    ranked_sources = [row["source"] for row in spec["extraction_contract"]["ranked_candidates"]]
    assert "src/flake8/plugins/pycodestyle.py:pycodestyle_logical" not in ranked_sources
