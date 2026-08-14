from __future__ import annotations

from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill


def _run_spec_writer(architecture_decision: dict):
    return run_role_skill(producer_for_artifact_type("TechnicalSpec"), architecture_decision=architecture_decision)


def test_spec_writer_demotes_arguments_builder_when_domain_target_exists():
    targets = ("app/main.py:arguments", "app/core.py:trim")
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer domain transform over CLI parser construction",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": list(targets),
        },
        "traceability": [
            {"source": source, "requirement": "Capability candidate requires TechnicalSpec."} for source in targets
        ],
        "source_context": {
            targets[0]: {
                "kind": "broad_function",
                "signature": {"args": [], "returns": "ArgumentParser"},
                "snippet": {"text": "def arguments(): return argparse.ArgumentParser()"},
                "callers": ["app/main.py:main"],
            },
            targets[1]: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "value", "annotation": "str"}], "returns": "str"},
                "snippet": {"text": "def trim(value): return value.strip()"},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == targets[1]
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "CLI/bootstrap support helper" in " ".join(ranked[targets[0]]["reasons"])


def test_semantic_rerank_uses_structural_contract_before_selecting_target():
    weak = "pkg/service.py:process_records"
    bounded = "pkg/contracts.py:parse_record"
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Select a structurally proven first slice",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [weak, bounded],
        },
        "traceability": [
            {"source": weak, "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": bounded, "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            weak: {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "records", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def process_records(records):\n    return external_call(records)"},
                "central_flow_node": True,
                "candidate_score": 100,
            },
            bounded: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "text", "annotation": "str"}], "returns": "dict[str, str]"},
                "snippet": {"text": "def parse_record(text: str) -> dict[str, str]:\n    return {'value': text.strip()}"},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == bounded
    assert spec["extraction_contract"]["semantic_quality"]["score"] >= 97


def test_spec_writer_demotes_dynamic_receiver_dispatch_below_bounded_serializer():
    dispatch = "domain.py:execute"
    serializer = "xml_serializer.py:serialize_model"
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer bounded serialization over opaque dispatch",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [dispatch, serializer],
        },
        "traceability": [
            {"source": source, "requirement": "Capability candidate requires TechnicalSpec."}
            for source in (dispatch, serializer)
        ],
        "source_context": {
            dispatch: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "method"}], "returns": ""},
                "snippet": {"text": "def execute(self, method=None):\n    return getattr(self, method)(**self.request.get_values())"},
            },
            serializer: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "model", "annotation": "Node"}], "returns": "str"},
                "snippet": {"text": "def serialize_model(model: Node) -> str:\n    return render(model)"},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == serializer
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "dynamic receiver dispatch" in " ".join(ranked[dispatch]["reasons"])


def test_spec_writer_prefers_stateful_xml_serializer_over_state_snapshot_hook():
    snapshot = "cot_node.py:__getstate__"
    serializer = "xml_serializer.py:serialize_model_to_cot"
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Select the project-domain serialization boundary",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {"scope": ["Prepare one spec."], "files_or_symbols": [snapshot, serializer]},
        "traceability": [
            {"source": source, "requirement": "Capability candidate requires TechnicalSpec."}
            for source in (snapshot, serializer)
        ],
        "source_context": {
            snapshot: {
                "kind": "unknown",
                "signature": {"args": [], "returns": "dict"},
                "snippet": {"text": "def __getstate__(self):\n    return self.__dict__"},
            },
            serializer: {
                "kind": "unknown",
                "signature": {"args": [{"name": "model"}], "returns": ""},
                "side_effects": ["memory_state"],
                "snippet": {"text": (
                    "def serialize_model_to_cot(self, model, level=0):\n"
                    "    xml = Element('event')\n"
                    "    model.type = normalize(model.type)\n"
                    "    return etree.tostring(xml) if level == 0 else xml"
                )},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == serializer
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "root and nested serialization outputs" in " ".join(ranked[serializer]["reasons"])


def test_spec_writer_accepts_source_proven_route_iterator_in_middleware():
    target = "pkg/middleware.py:_flatten_routes"
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Stabilize framework route compatibility",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {"scope": ["Prepare one spec."], "files_or_symbols": [target]},
        "traceability": [{"source": target, "requirement": "Capability requires TechnicalSpec."}],
        "source_context": {
            target: {
                "kind": "unknown",
                "signature": {"args": [{"name": "routes", "annotation": "Sequence[BaseRoute]"}], "returns": "Iterator[BaseRoute]"},
                "snippet": {"text": (
                    "def _flatten_routes(routes: Sequence[BaseRoute]) -> Iterator[BaseRoute]:\n"
                    "    for route in routes:\n        yield route"
                )},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == target
    assert spec["extraction_contract"]["semantic_quality"]["score"] >= 97


def test_spec_writer_demotes_test_suite_harness_when_product_event_target_exists():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer event dispatch contract over test harness assembly",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["src/zope/event/tests.py:test_suite", "src/zope/event/__init__.py:notify"],
        },
        "traceability": [
            {"source": "src/zope/event/tests.py:test_suite", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "src/zope/event/__init__.py:notify", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "src/zope/event/tests.py:test_suite": {
                "kind": "central_flow_node",
                "signature": {"args": [], "returns": "TestSuite"},
                "snippet": {"text": "def test_suite(): ..."},
                "candidate_level": "core_flow",
                "candidate_score": 90,
            },
            "src/zope/event/__init__.py:notify": {
                "kind": "central_flow_node",
                "signature": {"args": [{"name": "event", "annotation": "object"}], "returns": "None"},
                "snippet": {"text": "def notify(event): ..."},
                "candidate_level": "helper_transform",
                "candidate_score": 70,
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "src/zope/event/__init__.py:notify"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "constructor/logging/config helper" in " ".join(ranked["src/zope/event/tests.py:test_suite"]["reasons"])


def test_spec_writer_prefers_geospatial_array_contract_over_version_helper():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer geospatial data contract over version metadata helper",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": [
                "shapely/_version.py:git_pieces_from_vcs",
                "shapely/_ragged_array.py:_get_arrays_multilinestring",
            ],
        },
        "traceability": [
            {"source": "shapely/_version.py:git_pieces_from_vcs", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "shapely/_ragged_array.py:_get_arrays_multilinestring", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "shapely/_version.py:git_pieces_from_vcs": {
                "kind": "broad_function",
                "signature": {"args": [{"name": "root"}, {"name": "runner"}]},
                "snippet": {"text": "def git_pieces_from_vcs(root, runner): ..."},
                "callers": ["setup.py:get_versions"],
            },
            "shapely/_ragged_array.py:_get_arrays_multilinestring": {
                "kind": "unknown",
                "signature": {"args": [{"name": "arr", "annotation": "Geometry"}], "returns": "tuple"},
                "snippet": {"text": "def _get_arrays_multilinestring(arr): ..."},
                "callers": ["shapely/_ragged_array.py:to_ragged_array"],
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "shapely/_ragged_array.py:_get_arrays_multilinestring"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "generic introspection/debug helper" in " ".join(ranked["shapely/_version.py:git_pieces_from_vcs"]["reasons"])


def test_spec_writer_prefers_promise_error_contract_over_subclasshook():
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Prefer promise behavior over ABC metadata hook",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": ["vine/abstract.py:__subclasshook__", "vine/promises.py:throw"],
        },
        "traceability": [
            {"source": "vine/abstract.py:__subclasshook__", "requirement": "Capability candidate requires TechnicalSpec."},
            {"source": "vine/promises.py:throw", "requirement": "Capability candidate requires TechnicalSpec."},
        ],
        "source_context": {
            "vine/abstract.py:__subclasshook__": {
                "kind": "unknown",
                "signature": {"args": [{"name": "C"}]},
                "snippet": {"text": "def __subclasshook__(cls, C): ..."},
            },
            "vine/promises.py:throw": {
                "kind": "unknown",
                "signature": {"args": [{"name": "exc"}, {"name": "tb"}, {"name": "propagate"}], "returns": "None"},
                "snippet": {"text": "def throw(exc=None, tb=None, propagate=True): ..."},
            },
        },
    }

    spec = _run_spec_writer(adr)

    assert spec["extraction_contract"]["candidate"] == "vine/promises.py:throw"
    ranked = {row["source"]: row for row in spec["extraction_contract"]["ranked_candidates"]}
    assert "generic introspection/debug helper" in " ".join(ranked["vine/abstract.py:__subclasshook__"]["reasons"])
