import logging
from pathlib import Path

from runtime.executable_acceptance_isolation import load_source_isolated_callable


def test_source_isolated_logging_factory_preserves_safe_base_and_fakes_client(
    tmp_path: Path,
):
    source = tmp_path / "logging_adapter.py"
    source.write_text(
        "import logging\n"
        "from unavailable_search import SearchClient\n\n"
        "class SearchHandler(logging.Handler):\n"
        "    def __init__(self, endpoint=None):\n"
        "        super().__init__(level=0)\n"
        "        self.client = SearchClient(endpoint)\n\n"
        "def setup_search_handler(endpoint=None):\n"
        "    handler = SearchHandler(endpoint)\n"
        "    logging.getLogger('transport').setLevel(logging.WARNING)\n"
        "    return handler\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "setup_search_handler")
    handler = loaded["callable"]()

    assert loaded["reason"] == ""
    assert isinstance(handler, logging.Handler)
    assert bool(handler.client) is False


def test_source_isolated_method_does_not_import_unrun_constructor_dependency(
    tmp_path: Path,
):
    source = tmp_path / "formatter.py"
    source.write_text(
        "import unavailable_transport\n\n"
        "class Formatter:\n"
        "    def __init__(self):\n"
        "        self.client = unavailable_transport.Client()\n"
        "        self.prefix = 'live'\n\n"
        "    def format_record(self, record):\n"
        "        return f\"{self.prefix}:{record['event']}\"\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "Formatter.format_record")
    result = loaded["callable"]({"event": "ready"})

    assert loaded["reason"] == ""
    assert "ready" in result
    assert "client" not in loaded["method_instance_attributes"]
