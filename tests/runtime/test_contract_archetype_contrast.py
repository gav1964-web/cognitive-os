from runtime.contract_archetype_inference import matching_archetypes
from runtime.target_quality import semantic_target_quality_report


def test_adapter_name_does_not_imply_protocol_or_search_contract():
    matches = matching_archetypes(
        "logging_handlers/opensearch.py:setup_opensearch_handler"
    )

    ids = {row["id"] for row in matches}
    assert "protocol_command_handler" not in ids
    assert "search_backend_query_boundary" not in ids
    assert "logging_adapter_factory" in ids


def test_logging_sink_requires_qualified_owner_and_path_context():
    matches = matching_archetypes(
        "ExtendedJournalHandler/circus_journal.py:JournalStream.__call__"
    )

    assert "logging_sink_adapter" in {row["id"] for row in matches}
    assert not matching_archetypes("domain/model.py:Value.__call__")


def test_target_quality_uses_structural_owner_for_method_archetype():
    report = semantic_target_quality_report(
        "ExtendedJournalHandler/circus_journal.py:__call__",
        structural_evidence={"owner_class": "JournalStream"},
    )

    assert "logging_sink_adapter" in report["contract_archetype_ids"]


def test_logging_record_projection_requires_handler_owner():
    target = "splunk_handler/__init__.py:SplunkHandler.format_record"

    assert "logging_record_projection" in {
        row["id"] for row in matching_archetypes(target)
    }
    assert not matching_archetypes("domain/model.py:Model.format_record")
