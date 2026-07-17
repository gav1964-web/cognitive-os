from __future__ import annotations

from runtime.role_skills import run_spec_writer_skill


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

    spec = run_spec_writer_skill(architecture_decision=adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/providers/factory.py:build_providers_from_config"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    low_value_reasons = " ".join(ranked["pkg/worker/base.py:__init__"]["reasons"])
    assert "constructor/logging/config helper" in low_value_reasons


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

    spec = run_spec_writer_skill(architecture_decision=adr)

    assert spec["extraction_contract"]["candidate"] == "tinydb/table.py:search"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    write_reasons = " ".join(ranked["tinydb/storages.py:write"]["reasons"])
    assert "write/update/delete operation" in write_reasons


def test_spec_writer_prefers_database_search_over_generic_get_and_storage_adapter():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate database domain target ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "tinydb/table.py:get",
                "tinydb/table.py:search",
                "tinydb/storages.py:read",
            ],
        },
        "traceability": [
            {"source": "tinydb/table.py:get", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "tinydb/table.py:search", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "tinydb/storages.py:read", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "tinydb/table.py:get": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "doc_id", "annotation": "int"}], "returns": "Document | None"},
                "snippet": {"text": "def get(doc_id): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 96,
            },
            "tinydb/table.py:search": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "cond", "annotation": "QueryLike"}], "returns": "list[Document]"},
                "snippet": {"text": "def search(cond): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
            "tinydb/storages.py:read": {
                "kind": "central_flow_node",
                "signature": {"args": [], "returns": "dict"},
                "snippet": {"text": "def read(): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 94,
            },
        },
    }

    spec = run_spec_writer_skill(architecture_decision=adr)

    assert spec["extraction_contract"]["candidate"] == "tinydb/table.py:search"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    search_reasons = " ".join(ranked["tinydb/table.py:search"]["reasons"])
    get_reasons = " ".join(ranked["tinydb/table.py:get"]["reasons"])
    storage_reasons = " ".join(ranked["tinydb/storages.py:read"]["reasons"])
    assert "query/condition contract" in search_reasons
    assert "generic accessor" in get_reasons
    assert "storage adapter" in storage_reasons


def test_spec_writer_prefers_representative_lifecycle_slice_over_domain_utility():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate representative domain slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap",
                "spyder/api/widgets/main_widget.py:create_window",
            ],
        },
        "traceability": [
            {"source": "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "spyder/api/widgets/main_widget.py:create_window", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap": {
                "kind": "unknown",
                "signature": {
                    "args": [
                        {"name": "svg", "annotation": "str"},
                        {"name": "scale", "annotation": "float"},
                    ],
                    "returns": "QPixmap",
                },
                "snippet": {"text": "def svg_to_scaled_pixmap(svg, scale): ..."},
            },
            "spyder/api/widgets/main_widget.py:create_window": {
                "kind": "unknown",
                "signature": {"args": [], "returns": "QMainWindow"},
                "snippet": {"text": "def create_window(): ..."},
            },
        },
    }

    spec = run_spec_writer_skill(architecture_decision=adr)

    assert spec["extraction_contract"]["candidate"] == "spyder/api/widgets/main_widget.py:create_window"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    lifecycle_reasons = " ".join(ranked["spyder/api/widgets/main_widget.py:create_window"]["reasons"])
    utility_reasons = " ".join(ranked["spyder/api/widgets/mixins.py:svg_to_scaled_pixmap"]["reasons"])
    assert "representative domain flow/lifecycle slice" in lifecycle_reasons
    assert "domain utility/helper" in utility_reasons
