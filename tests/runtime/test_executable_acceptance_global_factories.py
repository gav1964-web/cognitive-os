from pathlib import Path

from runtime.executable_acceptance_isolation import load_source_isolated_callable
from runtime.executable_acceptance_samples import positive_samples_execute


def test_source_isolation_replaces_configured_external_client_factory(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text(
        "from unavailable_cloud import datastore\n"
        "client = datastore.Client()\n\n"
        "def fetch(key):\n"
        "    query = client.query(kind='record')\n"
        "    query.key_filter(client.key('record', key))\n"
        "    return next(query.fetch(limit=1), None)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "fetch")

    assert loaded["reason"] == ""
    assert loaded["callable"]("sample") is None


def test_bare_optional_result_contract_accepts_none():
    obligations = [{
        "target": "service.py:fetch",
        "kind": "positive_contract_case",
        "given": {},
        "expect": {"result": "Optional"},
    }]

    assert positive_samples_execute(lambda: None, "service.py:fetch", obligations)
