from __future__ import annotations

from tests.runtime.source_contract_semantics_helpers import *

def test_session_add_proves_database_side_effect():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "session"}, {"name": "value"}]},
        "snippet": "def add_value(session, value):\n    record = Record(value=value)\n    session.add(record)",
    })

    assert evidence["observed_side_effects"] == ["database"]


def test_receiver_request_dispatch_proves_delegated_result():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "method"}]},
        "snippet": "def execute(self, method=None):\n    return getattr(self, method)(**self.request.get_values())",
    })

    assert evidence["inferred_output_type"] == "DispatchedResult"
    assert evidence["output_inference_basis"] == "return_expression"
    assert evidence["dynamic_dispatch"] is True


def test_receiver_request_dispatch_is_visible_when_response_is_returned_separately():
    evidence = infer_source_contract({
        "snippet": (
            "def execute(self, method=None):\n"
            "    getattr(self, method)(**self.request.get_values())\n"
            "    return self.response"
        ),
    })

    assert evidence["inferred_output_type"] == "AttributeValue"
    assert evidence["dynamic_dispatch"] is True


def test_recursive_xml_serializer_proves_root_and_nested_output_shapes():
    evidence = infer_source_contract({
        "snippet": (
            "def serialize(self, model, tag='event', level=0):\n"
            "    xml = Element(tag)\n"
            "    return etree.tostring(xml) if level == 0 else xml"
        ),
    })

    assert evidence["inferred_output_type"] == "Union[XMLNodeLike, bytes]"
    assert evidence["output_inference_basis"] == "return_expression"


def test_read_only_session_and_local_append_do_not_prove_database_write():
    query = infer_source_contract({
        "signature": {"args": [{"name": "session"}]},
        "snippet": "def rows(session):\n    return session.query(Record).all()",
    })
    local = infer_source_contract({
        "signature": {"args": [{"name": "values"}, {"name": "value"}]},
        "snippet": "def append(values, value):\n    values.append(value)",
    })

    assert query["observed_side_effects"] == []
    assert local["observed_side_effects"] == ["memory_state"]
