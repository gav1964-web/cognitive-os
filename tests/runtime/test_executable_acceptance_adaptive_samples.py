from runtime.executable_acceptance_isolation import load_source_isolated_callable
from runtime.executable_acceptance_support import positive_samples_execute


def test_positive_sample_executes_generic_awaitable():
    class AwaitableResult:
        def __await__(self):
            async def complete():
                return "ready"

            return complete().__await__()

    obligations = [{
        "target": "worker.py:run",
        "kind": "positive_contract_case",
        "given": {},
        "expect": {"return_value": "ready"},
    }]

    assert positive_samples_execute(
        lambda: AwaitableResult(), "worker.py:run", obligations
    ) is True


def test_source_isolated_method_infers_mapping_receiver_attribute(tmp_path):
    source = tmp_path / "widget.py"
    source.write_text(
        "class Widget:\n"
        "    def update(self, key):\n"
        "        item = self._widgets.get(key)\n"
        "        if item is None:\n"
        "            return None\n"
        "        return item.value\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "update")

    assert loaded["reason"] == ""
    assert loaded["callable"]("missing") is None
    assert loaded["method_instance_attributes"] == {"_widgets": {}}
