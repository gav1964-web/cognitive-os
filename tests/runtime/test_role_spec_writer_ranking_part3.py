from __future__ import annotations
from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill
def _run_spec_writer(architecture_decision: dict):
    return run_role_skill(producer_for_artifact_type("TechnicalSpec"), architecture_decision=architecture_decision)

def test_spec_writer_shapes_llm_repair_hypothesis_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate repair-loop contract shape",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable repair-loop TechnicalSpec."],
            "files_or_symbols": [
                "AutoFix/auto_dev_agent.py:send_to_model",
                "AutoFix/auto_dev_agent.py:write_files",
                "AutoFix/auto_dev_agent.py:docker_run",
            ],
            "first_slice": {
                "name": "repair_attempt_contract_slice",
                "knowledge_rule": "llm_auto_repair_loop",
                "targets": [
                    "AutoFix/auto_dev_agent.py:send_to_model",
                    "AutoFix/auto_dev_agent.py:write_files",
                    "AutoFix/auto_dev_agent.py:docker_run",
                ],
                "steps": ["Define repair contracts.", "Validate model JSON.", "Verify in Docker."],
            },
        },
        "traceability": [
            {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "requirement": "Define repair contracts.",
                "target": "AutoFix/auto_dev_agent.py:send_to_model",
            }
        ],
        "source_context": {
            "AutoFix/auto_dev_agent.py:send_to_model": {
                "kind": "unknown",
                "signature": {"args": [{"name": "error_text", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def send_to_model(self, error_text): ..."},
                "side_effects": ["filesystem", "memory_state"],
            },
            "AutoFix/auto_dev_agent.py:write_files": {
                "kind": "unknown",
                "signature": {"args": [{"name": "updates", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def write_files(self, updates): ..."},
                "side_effects": ["filesystem"],
            },
            "AutoFix/auto_dev_agent.py:docker_run": {
                "kind": "unknown",
                "signature": {"args": [], "returns": ""},
                "snippet": {"text": "def docker_run(self): ..."},
                "side_effects": ["subprocess", "memory_state"],
            },
        },
    }

    spec = _run_spec_writer(adr)
    contract = spec["extraction_contract"]

    assert contract["candidate"] == "AutoFix/auto_dev_agent.py:send_to_model"
    assert contract["semantic_quality"]["status"] == "strong"
    assert contract["contract_family"] == "llm_repair_hypothesis_boundary"
    assert "failure_evidence" in contract["input_contract"]
    assert "model_patch_proposal" in contract["output_contract"]
    assert "invalid_model_json" in contract["failure_modes"]
    assert contract["side_effects"]["requires_validation_gate"] is True


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

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "spyder/api/widgets/main_widget.py:create_window"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    lifecycle_reasons = " ".join(ranked["spyder/api/widgets/main_widget.py:create_window"]["reasons"])
    utility_reasons = " ".join(ranked["spyder/api/widgets/mixins.py:svg_to_scaled_pixmap"]["reasons"])
    assert "representative domain flow/lifecycle slice" in lifecycle_reasons
    assert "domain utility/helper" in utility_reasons


def test_spec_writer_demotes_request_dispatcher_boundary():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate transport project first slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable transport capability extraction spec."],
            "files_or_symbols": [
                "httpcore/_async/http2.py:handle_async_request",
                "httpcore/_async/socks_proxy.py:_init_socks5_connection",
            ],
        },
        "traceability": [
            {
                "source": "httpcore/_async/http2.py:handle_async_request",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
            {
                "source": "httpcore/_async/socks_proxy.py:_init_socks5_connection",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "httpcore/_async/http2.py:handle_async_request": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "request", "annotation": "Request"}], "returns": "Response"},
                "snippet": {"text": "async def handle_async_request(request): ..."},
            },
            "httpcore/_async/socks_proxy.py:_init_socks5_connection": {
                "kind": "unknown",
                "signature": {
                    "args": [{"name": "stream", "annotation": "AsyncNetworkStream"}],
                    "returns": "AsyncNetworkStream",
                },
                "snippet": {"text": "async def _init_socks5_connection(stream): ..."},
                "callers": ["httpcore/_async/socks_proxy.py:handle_async_request"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "httpcore/_async/socks_proxy.py:_init_socks5_connection"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    dispatcher_reasons = " ".join(ranked["httpcore/_async/http2.py:handle_async_request"]["reasons"])
    assert "request dispatcher boundary" in dispatcher_reasons


def test_spec_writer_demotes_path_accessor_over_validator_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate build backend first slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable build capability extraction spec."],
            "files_or_symbols": [
                "src/build/_builder.py:metadata_path",
                "src/build/__main__.py:_validate_sdist_archive",
            ],
        },
        "traceability": [
            {"source": "src/build/_builder.py:metadata_path", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "src/build/__main__.py:_validate_sdist_archive",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "src/build/_builder.py:metadata_path": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "name", "annotation": "str"}], "returns": "Path"},
                "snippet": {"text": "def metadata_path(name): ..."},
            },
            "src/build/__main__.py:_validate_sdist_archive": {
                "kind": "unknown",
                "signature": {"args": [{"name": "path", "annotation": "Path"}], "returns": "None"},
                "snippet": {"text": "def _validate_sdist_archive(path): ..."},
                "callers": ["src/build/__main__.py:_build"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "src/build/__main__.py:_validate_sdist_archive"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    accessor_reasons = " ".join(ranked["src/build/_builder.py:metadata_path"]["reasons"])
    assert "small helper is less representative" in accessor_reasons


def test_spec_writer_demotes_operational_lifecycle_wrapper_over_builder_contract():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate package operation first slice ranking",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/commands/install.py:install",
                "pkg/auth/digest.py:build_digest_header",
            ],
        },
        "traceability": [
            {"source": "pkg/commands/install.py:install", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/auth/digest.py:build_digest_header", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "pkg/commands/install.py:install": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "options", "annotation": "InstallOptions"}], "returns": "None"},
                "snippet": {"text": "def install(options): ..."},
            },
            "pkg/auth/digest.py:build_digest_header": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "challenge", "annotation": "dict"}], "returns": "str"},
                "snippet": {"text": "def build_digest_header(challenge): ..."},
                "callers": ["pkg/sessions.py:request"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/auth/digest.py:build_digest_header"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    install_reasons = " ".join(ranked["pkg/commands/install.py:install"]["reasons"])
    assert "operational lifecycle/mutation wrapper" in install_reasons


def test_spec_writer_semantic_rerank_prefers_stronger_bounded_slice_when_close():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Calibrate semantic rerank",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "pkg/worker.py:process_everything",
                "pkg/contracts.py:parse_payload",
            ],
        },
        "traceability": [
            {"source": "pkg/worker.py:process_everything", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "pkg/contracts.py:parse_payload", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "pkg/worker.py:process_everything": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "dict"},
                "snippet": {"text": "def process_everything(payload): ..."},
                "central_flow_node": True,
                "candidate_score": 100,
            },
            "pkg/contracts.py:parse_payload": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "text", "annotation": "str"}], "returns": "Payload"},
                "snippet": {"text": "def parse_payload(text): ..."},
                "side_effects": ["filesystem_read"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "pkg/contracts.py:parse_payload"
    assert spec["extraction_contract"]["semantic_quality"]["status"] == "strong"
    assert "semantic rerank selected" in spec["extraction_contract"]["selection_reason"]


def test_spec_writer_blocks_when_first_slice_has_no_safe_targets_and_only_tests_are_available():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Do not build a spec from test-only evidence",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": {
            "name": "automation_task_execution_slice",
            "goal": "No Python implementation target exists.",
            "targets": [],
            "steps": ["Define contract only if a source-backed target exists."],
        },
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["test/test_default.py:test_default_not_callable"],
            "first_slice": {
                "name": "automation_task_execution_slice",
                "goal": "No Python implementation target exists.",
                "targets": [],
                "steps": ["Define contract only if a source-backed target exists."],
            },
        },
        "traceability": [
            {"source": "test/test_default.py:test_default_not_callable", "requirement": "Capability candidate requires TechnicalSpec."}
        ],
        "source_context": {
            "test/test_default.py:test_default_not_callable": {
                "kind": "test_function",
                "signature": {"args": [], "returns": "None"},
                "snippet": {"text": "def test_default_not_callable(): ..."},
            }
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["work_plan_contract"]["status"] == "blocked_no_first_slice"
    assert spec["extraction_contract"]["status"] == "blocked_no_safe_candidate"
    assert spec["extraction_contract"]["candidate"] is None
    assert spec["source_evidence"] == []
