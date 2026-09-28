from __future__ import annotations

from tests.runtime.executable_acceptance_adaptive_samples_helpers import *

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


def test_source_isolated_method_infers_numeric_receiver_attribute(tmp_path):
    source = tmp_path / "reader.py"
    source.write_text(
        "class Reader:\n"
        "    def reset(self):\n"
        "        self._order = list(range(self._count))\n"
        "        return self._order\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "Reader.reset")

    assert loaded["callable"]() == [0]
    assert loaded["method_instance_attributes"]["_count"] == 1


def test_source_isolated_method_infers_array_and_successful_boolean_receivers(tmp_path):
    source = tmp_path / "strategy.py"
    source.write_text(
        "import numpy as np\n"
        "class Strategy:\n"
        "    def check(self, number):\n"
        "        if number > self.pool_size: raise ValueError('too many')\n"
        "    def query(self, number, embeddings):\n"
        "        self.check(number)\n"
        "        paths = np.array(self.path_mapping)\n"
        "        if self.enabled:\n"
        "            return paths[embeddings.mean(0).argsort()[:int(number)]]\n"
        "        else:\n"
        "            raise ValueError('disabled')\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "Strategy.query")

    assert loaded["method_instance_attributes"]["enabled"] is True
    assert loaded["method_instance_attributes"]["pool_size"] == 16
    assert loaded["method_instance_attributes"]["path_mapping"]["__fixture__"] == "numpy_array"


def test_infers_numpy_fixture_dimension_from_reduction_axis(tmp_path):
    source = tmp_path / "uncertainty.py"
    source.write_text(
        "import numpy as np\n"
        "def disagreement(embeddings):\n"
        "    mean = embeddings.mean(0)\n"
        "    return (-embeddings * np.log(embeddings)).sum(2).mean(0) - mean.sum(1)\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "disagreement")

    assert inferred["embeddings"]["source"] == "ast_array_axis:2"
    assert inferred["embeddings"]["value"]["__fixture__"] == "numpy_array"


def test_source_isolated_method_infers_required_mapping_key(tmp_path):
    source = tmp_path / "registry.py"
    source.write_text(
        "class Registry:\n"
        "    def remove(self, node_id):\n"
        "        self._items.pop(node_id)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "Registry.remove")

    node_id = "0" * 64
    assert loaded["callable"](node_id) is None
    assert node_id in loaded["method_instance_attributes"]["_items"]


def test_source_isolation_falls_back_for_newer_stdlib_symbol(tmp_path):
    source = tmp_path / "clock.py"
    source.write_text(
        "from datetime import UTC, datetime\n"
        "def now():\n"
        "    return datetime.now(UTC)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "now")

    assert loaded["reason"] == ""
    assert loaded["callable"]().utcoffset().total_seconds() == 0


def test_infers_chainable_parameter_protocol_fixture(tmp_path):
    source = tmp_path / "tree_output.py"
    source.write_text(
        "def add_components(branch, components):\n"
        "    for name in components:\n"
        "        branch.add(name).add('source')\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "add_components")

    assert inferred["branch"] == {
        "value": {"__fixture__": "safe_method_attribute"},
        "source": "ast_parameter_callable_protocol:add",
    }


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


def test_variadic_keyword_factory_without_required_parameters_accepts_empty_input():
    def create(**kwargs):
        return kwargs

    obligations = [
        {"target": "client.py:create", "kind": "positive_contract_case", "given": {"kwargs": {}}},
        {"target": "client.py:create", "kind": "malformed_input_case", "given": {}},
    ]

    assert signature_needs_negative_case(create, "client.py:create", obligations) is False


def test_bound_method_synthetic_receiver_is_not_a_required_user_input():
    def isolated_method(**kwargs):
        return kwargs.get("receiver_state", "fixture-owned")

    obligations = [
        {
            "target": "client.py:info",
            "kind": "positive_contract_case",
            "given": {"receiver_state": "sample"},
        },
        {"target": "client.py:info", "kind": "malformed_input_case", "given": {}},
    ]

    assert signature_needs_negative_case(
        isolated_method,
        "client.py:info",
        obligations,
        synthetic_input_keys={"receiver_state"},
    ) is False


def test_explicit_receiver_state_contract_still_requires_input():
    def transform(receiver_state):
        return receiver_state

    obligations = [
        {
            "target": "client.py:transform",
            "kind": "positive_contract_case",
            "given": {"receiver_state": "sample"},
        },
        {"target": "client.py:transform", "kind": "malformed_input_case", "given": {}},
    ]

    assert signature_needs_negative_case(transform, "client.py:transform", obligations) is True


def test_generated_platformdirs_version_profile_preserves_real_package_import(tmp_path):
    package = tmp_path / "src" / "platformdirs"
    package.mkdir(parents=True)
    source = package / "__init__.py"
    source.write_text(
        "from .version import __version__\n"
        "def current_version(): return __version__\n",
        encoding="utf-8",
    )

    with import_path(tmp_path, source):
        loaded = load_supported_callable(tmp_path, "src/platformdirs/__init__.py", "current_version", source)

    assert loaded["reason"] == ""
    assert loaded.get("source_isolated") is not True
    assert loaded["callable"]() == "0.0.0"


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


def test_infers_sequence_shape_from_parameter_attribute_unpack(tmp_path):
    path = tmp_path / "module.py"
    path.write_text(
        "def ratio(image):\n"
        "    width, height = image.size\n"
        "    return min(width / height, height / width)\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "ratio") == {
        "image": {
            "value": {
                "__fixture__": "declared_model",
                "type": "AcceptanceInput",
                "fields": {"size": [1.0, 1.0]},
            },
            "source": "ast_parameter_attribute_unpack",
        }
    }


def test_structural_shape_overrides_generic_scalar_contract_sample(tmp_path):
    from runtime.executable_acceptance_support import positive_case_binding

    def reshape(values, shape):
        rows, columns = shape
        return values, rows, columns

    obligations = [
        {
            "target": "module.py:reshape",
            "kind": "positive_contract_case",
            "given": {"values": 1, "shape": 1},
        }
    ]
    inferred = {
        "shape": {"value": [1.0, 1.0], "source": "ast_parameter_unpack"},
    }

    binding = positive_case_binding(reshape, "module.py:reshape", obligations, inferred)

    assert binding["overrides"] == {"shape": [1.0, 1.0]}
