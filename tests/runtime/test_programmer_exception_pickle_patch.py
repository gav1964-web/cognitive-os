import pickle
import sys
import types

from runtime.programmer_exception_pickle_patch import exception_pickle_reconstruction_patch


def test_reuses_direct_constructor_state_for_exception_reconstruction():
    source = (
        "class LocationParseError(ValueError):\n"
        "    def __init__(self, location):\n"
        "        message = f'Failed to parse: {location}'\n"
        "        super().__init__(message)\n"
        "        self.location = location\n"
    )
    patch = exception_pickle_reconstruction_patch(
        source,
        class_name="LocationParseError",
        recipe={
            "required_constructor_inputs": ["location"],
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
        },
    )

    assert patch is not None
    module_name = "test_pickle_patch_fixture"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    try:
        exec(patch["source"], module.__dict__)
        exception_type = module.LocationParseError
        exception = exception_type("fake location")
        restored = pickle.loads(pickle.dumps(exception))
    finally:
        sys.modules.pop(module_name, None)

    assert restored.location == "fake location"
    assert str(restored) == "Failed to parse: fake location"


def test_reuses_direct_state_when_super_init_has_no_arguments():
    source = (
        "class MessageOnlyError(Exception):\n"
        "    def __init__(self, message):\n"
        "        super().__init__()\n"
        "        self.message = message\n"
        "\n"
        "    def __str__(self):\n"
        "        return str(self.message)\n"
    )
    patch = exception_pickle_reconstruction_patch(
        source,
        class_name="MessageOnlyError",
        recipe={
            "required_constructor_inputs": ["message"],
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
        },
    )

    assert patch is not None
    module_name = "test_pickle_patch_zero_arg_super_fixture"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    try:
        exec(patch["source"], module.__dict__)
        restored = pickle.loads(pickle.dumps(module.MessageOnlyError("sample failure")))
    finally:
        sys.modules.pop(module_name, None)

    assert restored.message == "sample failure"
    assert str(restored) == "sample failure"


def test_reuses_direct_state_when_super_init_has_multiple_arguments():
    source = (
        "class ServiceNotFound(Exception):\n"
        "    def __init__(self, domain, service):\n"
        "        super().__init__(self, f'Service {domain}.{service} not found')\n"
        "        self.domain = domain\n"
        "        self.service = service\n"
        "\n"
        "    def __str__(self):\n"
        "        return f'Unable to find service {self.domain}.{self.service}'\n"
    )
    patch = exception_pickle_reconstruction_patch(
        source,
        class_name="ServiceNotFound",
        recipe={
            "required_constructor_inputs": ["domain", "service"],
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
        },
    )

    assert patch is not None
    module_name = "test_pickle_patch_multi_arg_super_fixture"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    try:
        exec(patch["source"], module.__dict__)
        restored = pickle.loads(pickle.dumps(module.ServiceNotFound("light", "on")))
    finally:
        sys.modules.pop(module_name, None)

    assert restored.domain == "light"
    assert restored.service == "on"
    assert str(restored) == "Unable to find service light.on"


def test_reuses_direct_state_for_keyword_only_constructor_inputs():
    source = (
        "class KeywordOnlyError(RuntimeError):\n"
        "    def __init__(self, *, message, context):\n"
        "        self.message = message\n"
        "        self.context = context\n"
        "        super().__init__(f'{message}: {context}')\n"
    )
    patch = exception_pickle_reconstruction_patch(
        source,
        class_name="KeywordOnlyError",
        recipe={
            "required_constructor_inputs": ["message", "context"],
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
            "allow_keyword_only_state_reducer": True,
        },
    )

    assert patch is not None
    assert "BaseException.__new__" in patch["source"]
    module_name = "test_pickle_patch_keyword_only_fixture"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    try:
        exec(patch["source"], module.__dict__)
        exception = module.KeywordOnlyError(message="sample-message", context="sample-context")
        restored = pickle.loads(pickle.dumps(exception))
    finally:
        sys.modules.pop(module_name, None)

    assert restored.message == "sample-message"
    assert restored.context == "sample-context"
    assert str(restored) == "sample-message: sample-context"


def test_reuse_strategy_rejects_unstored_constructor_input():
    source = (
        "class PayloadError(RuntimeError):\n"
        "    def __init__(self, payload, code):\n"
        "        self.payload = payload\n"
        "        super().__init__(f'{code}: {payload}')\n"
    )

    assert exception_pickle_reconstruction_patch(
        source,
        class_name="PayloadError",
        recipe={
            "required_constructor_inputs": ["payload", "code"],
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
        },
    ) is None
