from runtime.executable_acceptance_contract_inference import infer_argument_samples
from runtime.executable_acceptance_isolation import load_source_isolated_callable
from runtime.executable_acceptance_support import positive_samples_execute, signature_needs_negative_case


def test_infers_callable_fixture_when_parameter_is_invoked(tmp_path):
    source = tmp_path / "formatter.py"
    source.write_text(
        "def format_text(text, transform=None):\n"
        "    return transform(text, strict=True) if transform else text\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "format_text")

    assert inferred["transform"] == {
        "value": {"__fixture__": "callable_identity"},
        "source": "ast_parameter_callable",
    }


def test_infers_empty_collection_for_sorted_parameter(tmp_path):
    source = tmp_path / "ordering.py"
    source.write_text(
        "def order(items):\n    return sorted(items, key=lambda item: item.rank)\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "order")

    assert inferred["items"] == {"value": [], "source": "ast_conversion:sorted"}


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


def test_source_isolated_method_stubs_delegated_transport(tmp_path):
    source = tmp_path / "client.py"
    source.write_text(
        "class Client:\n"
        "    def _post(self, path, payload):\n"
        "        raise RuntimeError('network must not run')\n"
        "    def send(self, user, body):\n"
        "        return self._post('/users/{}'.format(user), {'body': body})\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "send")

    assert loaded["callable"]("user", "hello") == {"accepted": True}
    assert loaded["method_instance_attributes"] == {
        "_post": {"__fixture__": "callable_transport_result"},
    }


def test_optional_receiver_fallback_does_not_require_missing_input_failure():
    def invalidate(access_token=None):
        return access_token or "receiver-token"

    obligations = [
        {"target": "client.py:invalidate", "kind": "positive_contract_case", "given": {"command": "sample"}},
        {"target": "client.py:invalidate", "kind": "malformed_input_case", "given": {}},
    ]

    assert signature_needs_negative_case(invalidate, "client.py:invalidate", obligations) is False


def test_infers_delimited_string_from_split_unpack(tmp_path):
    path = tmp_path / "module.py"
    path.write_text(
        "def extract(filename):\n"
        "    stem, extension = filename.removeprefix('backup-').split('_', 1)\n"
        "    return stem, extension\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "extract") == {
        "filename": {"value": "sample_sample", "source": "ast_split_unpack"}
    }


def test_infers_sequence_shape_from_parameter_unpack(tmp_path):
    path = tmp_path / "module.py"
    path.write_text(
        "def ratio(source_size, target_size):\n"
        "    sh, sw = source_size\n"
        "    th, tw = target_size\n"
        "    return sh / th, sw / tw\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "ratio") == {
        "source_size": {"value": [1.0, 1.0], "source": "ast_parameter_unpack"},
        "target_size": {"value": [1.0, 1.0], "source": "ast_parameter_unpack"},
    }


def test_string_formatting_does_not_override_literal_domain(tmp_path):
    path = tmp_path / "module.py"
    path.write_text(
        "def choose(mode):\n"
        "    if mode == 'longest': return 1\n"
        "    raise ValueError('unknown mode %r' % mode)\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "choose") == {
        "mode": {"value": "longest", "source": "ast_comparison_literal"}
    }
