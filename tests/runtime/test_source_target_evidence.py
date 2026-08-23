from runtime.source_target_evidence import source_target_evidence


def test_extracts_exact_top_level_callable(tmp_path):
    (tmp_path / "worker.py").write_text(
        "async def sync_items(client: Client, limit: int = 10) -> dict[str, int]:\n"
        "    rows = await client.fetch(limit)\n"
        "    return {'count': len(rows)}\n",
        encoding="utf-8",
    )

    evidence = source_target_evidence(tmp_path, "worker.py:sync_items")

    assert evidence["source"] == "worker.py:sync_items"
    assert evidence["signature"]["args"][0] == {"name": "client", "annotation": "Client"}
    assert evidence["signature"]["returns"] == "dict[str, int]"
    assert "await client.fetch" in evidence["snippet"]["text"]


def test_rejects_path_escape_and_nested_ambiguous_symbol(tmp_path):
    (tmp_path / "worker.py").write_text("class Worker:\n    def run(self):\n        return 1\n", encoding="utf-8")

    assert source_target_evidence(tmp_path, "../outside.py:run") == {}
    assert source_target_evidence(tmp_path, "worker.py:run") == {}


def test_extracts_class_qualified_method(tmp_path):
    (tmp_path / "worker.py").write_text(
        "class Worker:\n    def set_state(self, value: str):\n        self.value = value\n",
        encoding="utf-8",
    )

    evidence = source_target_evidence(tmp_path, "worker.py:Worker.set_state")

    assert evidence["node_kind"] == "method"
    assert evidence["snippet"]["owner_class"] == "Worker"
    assert evidence["snippet"]["target_binding"] == "method_symbol"
    assert evidence["snippet"]["structural_contract"]["state_mutation"] is True
    assert evidence["signature"]["args"][1] == {"name": "value", "annotation": "str"}
    assert "self.value = value" in evidence["snippet"]["text"]


def test_extracts_method_from_python2_compatible_source(tmp_path):
    (tmp_path / "legacy.py").write_text(
        "class Handler(object):\n"
        "    def format(self, record):\n"
        "        try:\n            return record.msg\n"
        "        except ValueError, exc:\n            return str(exc)\n",
        encoding="utf-8",
    )

    evidence = source_target_evidence(tmp_path, "legacy.py:Handler.format")

    assert evidence["snippet"]["owner_class"] == "Handler"
    assert evidence["parser_mode"]
