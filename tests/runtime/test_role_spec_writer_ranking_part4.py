from __future__ import annotations
from pathlib import Path
from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill
from runtime.project_benchmark import analyze_project
from runtime.configured_role_pipeline import artifact_by_type, run_configured_role_prefix
def _run_spec_writer(architecture_decision: dict):
    return run_role_skill(producer_for_artifact_type("TechnicalSpec"), architecture_decision=architecture_decision)


def test_tiny_top_level_script_gets_source_backed_module_target(tmp_path: Path):
    project = tmp_path / "opencv_tutorial"
    project.mkdir()
    (project / "README.md").write_text("OpenCV tutorial\n", encoding="utf-8")
    (project / "basics.py").write_text(
        "import cv2\n\nimage = cv2.imread('dog.png')\nprint(image.shape)\n",
        encoding="utf-8",
    )
    report = analyze_project(project)["project_map_report"]

    artifacts = run_configured_role_prefix(
        goal="GitHub Executor probe for tiny tutorial",
        project_report=report,
        until_artifact_type="TechnicalSpec",
    )
    spec = artifact_by_type(artifacts, "TechnicalSpec")

    assert spec["extraction_contract"]["candidate"] == "basics.py"
    assert spec["extraction_contract"].get("status") != "blocked_no_safe_candidate"
    assert spec["implementation_handoff"]["patch_scope"] == ["basics.py"]

def test_spec_writer_allows_profiled_runtime_wrapper_with_contract_family():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Allow profiled runtime wrapper when explicit contract family exists.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["sentry_sdk/integrations/asgi.py:_run_app"],
        },
        "traceability": [
            {
                "source": "sentry_sdk/integrations/asgi.py:_run_app",
                "requirement": "Capability candidate requires TechnicalSpec.",
            }
        ],
        "source_context": {
            "sentry_sdk/integrations/asgi.py:_run_app": {
                "kind": "broad_function",
                "signature": {
                    "args": [{"name": "app", "annotation": "ASGIApp"}],
                    "returns": "Awaitable[None]",
                },
                "snippet": {"text": "async def _run_app(app): ..."},
            }
        },
    }

    spec = _run_spec_writer(adr)

    contract = spec["extraction_contract"]
    assert contract["candidate"] == "sentry_sdk/integrations/asgi.py:_run_app"
    assert contract["contract_family"] == "asgi_app_wrapper_boundary"
    assert contract["input_contract"]
    assert contract["output_contract"]
    assert contract["validation_gates"]
    assert contract["failure_modes"]


def test_spec_writer_adds_domain_contract_family_for_ml_metric_target():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Build a specific contract for a model evaluation helper.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["sklearn/calibration.py:calibration_curve"],
        },
        "traceability": [
            {
                "source": "sklearn/calibration.py:calibration_curve",
                "requirement": "Capability candidate requires TechnicalSpec.",
            }
        ],
        "source_context": {
            "sklearn/calibration.py:calibration_curve": {
                "kind": "broad_function",
                "signature": {
                    "args": [
                        {"name": "y_true", "annotation": "ArrayLike"},
                        {"name": "y_prob", "annotation": "ArrayLike"},
                    ],
                    "returns": "tuple[ndarray, ndarray]",
                },
                "snippet": {"text": "def calibration_curve(y_true, y_prob): ..."},
            }
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "sklearn/calibration.py:calibration_curve"
    assert spec["extraction_contract"]["contract_family"] == "ml_metric_calibration_transform"
    assert spec["extraction_contract"]["semantic_quality"]["status"] == "strong"


def test_spec_writer_prefers_executable_ready_contract_over_runtime_object_boundary():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Choose first executable slice before object-heavy runtime boundary.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "botocore/client.py:_make_api_call",
                "flake8/plugins/finder.py:parse_plugin_options",
            ],
        },
        "traceability": [
            {"source": "botocore/client.py:_make_api_call", "requirement": "Capability candidate requires TechnicalSpec."},
            {
                "source": "flake8/plugins/finder.py:parse_plugin_options",
                "requirement": "Capability candidate requires TechnicalSpec.",
            },
        ],
        "source_context": {
            "botocore/client.py:_make_api_call": {
                "kind": "central_flow_node",
                "signature": {
                    "args": [
                        {"name": "operation_name", "annotation": "str"},
                        {"name": "api_params", "annotation": "dict"},
                    ],
                    "returns": "dict",
                },
                "candidate_level": "core_flow",
                "snippet": {"text": "def _make_api_call(self, operation_name, api_params): ..."},
            },
            "flake8/plugins/finder.py:parse_plugin_options": {
                "kind": "pure_transform",
                "signature": {
                    "args": [
                        {"name": "cfg", "annotation": "ConfigParser"},
                        {"name": "cfg_dir", "annotation": "str"},
                    ],
                    "returns": "PluginOptions",
                },
                "candidate_level": "helper_transform",
                "snippet": {"text": "def parse_plugin_options(cfg, cfg_dir): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}

    assert spec["extraction_contract"]["candidate"] == "flake8/plugins/finder.py:parse_plugin_options"
    assert "first executable slice" in " ".join(ranked["flake8/plugins/finder.py:parse_plugin_options"]["reasons"])
    assert "runtime object boundary" in " ".join(ranked["botocore/client.py:_make_api_call"]["reasons"])


def test_spec_writer_demotes_stateful_methods_seen_in_field_trials():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer executable helpers over stateful instance methods.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "arrow/parser.py:parse_iso",
                "arrow/parser.py:_build_datetime",
                "src/requests/auth.py:build_digest_header",
                "src/requests/sessions.py:resolve_redirects",
            ],
        },
        "traceability": [
            {"source": "arrow/parser.py:parse_iso", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "arrow/parser.py:_build_datetime", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "src/requests/auth.py:build_digest_header", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "src/requests/sessions.py:resolve_redirects", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "arrow/parser.py:parse_iso": {
                "kind": "method",
                "signature": {"args": [{"name": "datetime_string", "annotation": "str"}], "returns": "datetime"},
                "snippet": {"text": "def parse_iso(self, datetime_string): return self._parse_token(...)"},
            },
            "arrow/parser.py:_build_datetime": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "parts", "annotation": "dict"}], "returns": "datetime"},
                "snippet": {"text": "def _build_datetime(parts): return datetime(...)"},
            },
            "src/requests/auth.py:build_digest_header": {
                "kind": "method",
                "signature": {"args": [{"name": "method", "annotation": "str"}, {"name": "url", "annotation": "str"}]},
                "snippet": {"text": "def build_digest_header(self, method, url): return self._thread_local..."},
            },
            "src/requests/sessions.py:resolve_redirects": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "resp", "annotation": "Response"}], "returns": "Iterator[Response]"},
                "snippet": {"text": "def resolve_redirects(self, resp): yield prepared_request"},
            },
        },
    }

    spec = _run_spec_writer(adr)
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}

    assert ranked["arrow/parser.py:_build_datetime"]["score"] > ranked["arrow/parser.py:parse_iso"]["score"]
    assert ranked["src/requests/sessions.py:resolve_redirects"]["score"] > ranked["src/requests/auth.py:build_digest_header"]["score"]


def test_spec_writer_prefers_public_render_boundary_over_internal_closure_helper():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer stable presentation boundary over closure-heavy helper.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["rich/pretty.py:_traverse", "rich/pretty.py:traverse"],
        },
        "traceability": [
            {"source": "rich/pretty.py:_traverse", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "rich/pretty.py:traverse", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "rich/pretty.py:_traverse": {
                "kind": "nested_function",
                "signature": {"args": [{"name": "obj", "annotation": "Any"}], "returns": "Node"},
                "snippet": {"text": "def _traverse(obj, root=False, depth=0): return Node(...)"},
            },
            "rich/pretty.py:traverse": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "obj", "annotation": "Any"}], "returns": "Node"},
                "snippet": {"text": "def traverse(obj, max_depth=None): return _traverse(obj, root=True)"},
            },
        },
    }

    spec = _run_spec_writer(adr)
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}

    assert spec["extraction_contract"]["candidate"] == "rich/pretty.py:traverse"
    assert ranked["rich/pretty.py:traverse"]["score"] > ranked["rich/pretty.py:_traverse"]["score"]
    assert "internal closure helper" in " ".join(ranked["rich/pretty.py:_traverse"]["reasons"])


def test_spec_writer_demotes_ambiguous_method_symbol_without_class_binding():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer concrete parser helper over ambiguous method symbol.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["src/click/core.py:parse_args", "src/click/parser.py:_unpack_args"],
        },
        "traceability": [
            {"source": "src/click/core.py:parse_args", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "src/click/parser.py:_unpack_args", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "src/click/core.py:parse_args": {
                "kind": "method",
                "target_binding": "ambiguous_method_symbol",
                "signature": {"args": [{"name": "ctx", "annotation": "Context"}, {"name": "args", "annotation": "list[str]"}]},
                "snippet": {"text": "def parse_args(self, ctx, args): return args"},
            },
            "src/click/parser.py:_unpack_args": {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "args", "annotation": "list[str]"}], "returns": "tuple"},
                "snippet": {"text": "def _unpack_args(args): return args, []"},
            },
        },
    }

    spec = _run_spec_writer(adr)
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}

    assert spec["extraction_contract"]["candidate"] == "src/click/parser.py:_unpack_args"
    assert ranked["src/click/parser.py:_unpack_args"]["score"] > ranked["src/click/core.py:parse_args"]["score"]
    assert "ambiguous across classes" in " ".join(ranked["src/click/core.py:parse_args"]["reasons"])


def test_spec_writer_keeps_executable_ready_target_over_lower_scored_method():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer executable-ready Click helper over stateful parse method.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["src/click/_textwrap.py:_wrap_chunks", "src/click/core.py:handle_parse_result"],
        },
        "traceability": [
            {"source": "src/click/_textwrap.py:_wrap_chunks", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "src/click/core.py:handle_parse_result", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "src/click/_textwrap.py:_wrap_chunks": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "chunks", "annotation": "list[str]"}], "returns": "list[str]"},
                "snippet": {"text": "def _wrap_chunks(self, chunks): return chunks"},
            },
            "src/click/core.py:handle_parse_result": {
                "kind": "method",
                "signature": {"args": [{"name": "ctx", "annotation": "Context"}, {"name": "opts", "annotation": "Mapping"}]},
                "snippet": {"text": "def handle_parse_result(self, ctx, opts, args): return self.consume_value(ctx, opts)"},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "src/click/_textwrap.py:_wrap_chunks"


def test_spec_writer_semantic_review_allows_domain_central_helper_with_constraints():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Allow a pyparsing-style helper only with explicit semantic review evidence.",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable parser-helper capability extraction spec."],
            "files_or_symbols": ["pyparsing/helpers.py:one_of"],
            "first_slice": {
                "name": "first_slice_one_of",
                "targets": ["pyparsing/helpers.py:one_of"],
                "steps": ["Confirm bounded parser helper contract."],
            },
        },
        "traceability": [
            {"source": "pyparsing/helpers.py:one_of", "requirement": "Capability candidate requires TechnicalSpec."}
        ],
        "source_context": {
            "pyparsing/helpers.py:one_of": {
                "kind": "broad_function",
                "signature": {
                    "args": [{"name": "strs", "annotation": "list[str]"}, {"name": "caseless", "annotation": "bool"}],
                    "returns": "ParserElement",
                },
                "snippet": {"text": "def one_of(strs, caseless=False): return ParserElement()"},
            }
        },
    }

    spec = _run_spec_writer(adr)
    contract = spec["extraction_contract"]

    assert contract["candidate"] == "pyparsing/helpers.py:one_of"
    assert contract["semantic_quality"]["status"] == "suspicious"
    assert contract["semantic_review"]["status"] == "approved_with_constraints"
