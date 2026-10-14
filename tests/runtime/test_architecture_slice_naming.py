from __future__ import annotations

from runtime.architecture_slice_naming import semantic_first_slice_name


def test_semantic_first_slice_name_uses_profiled_target_boundary() -> None:
    name = semantic_first_slice_name(
        "configuration_parse_lookup_slice",
        ["src/apscheduler/datastores/mongodb.py:acquire_jobs"],
    )

    assert name == "scheduled_job_acquisition_slice"


def test_semantic_first_slice_name_preserves_specific_name() -> None:
    name = semantic_first_slice_name(
        "async_protocol_event_slice",
        ["src/anyio/_core/_sockets.py:connect_tcp"],
    )

    assert name == "async_protocol_event_slice"
