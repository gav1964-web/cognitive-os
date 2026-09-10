from __future__ import annotations

from runtime.programmer_structured_edit import apply_structured_replacement, replacement_shape_errors


def test_structured_replacement_preserves_file_context_and_signature():
    original = "COMMANDS = {'run'}\n\ndef resolve(value):\n    return value\n"
    replacement = "def resolve(value):\n    return value.upper()\n"

    patched, reason = apply_structured_replacement(original, "main.py:resolve", replacement)

    assert reason == "structured_function_replacement_applied"
    assert patched == "COMMANDS = {'run'}\n\ndef resolve(value):\n    return value.upper()\n"


def test_structured_replacement_preserves_method_indentation():
    original = "class Service:\n    def resolve(self, value):\n        return value\n"
    replacement = "def resolve(self, value):\n    return value.strip()\n"

    patched, reason = apply_structured_replacement(original, "main.py:resolve", replacement)

    assert reason == "structured_function_replacement_applied"
    assert "    def resolve(self, value):\n        return value.strip()" in str(patched)


def test_structured_replacement_resolves_qualified_method():
    original = "class First:\n    def render(self, value):\n        return value\n\nclass Second:\n    def render(self, value):\n        return str(value)\n"
    replacement = "def render(self, value):\n    return value.upper()"

    patched, reason = apply_structured_replacement(original, "module.py:First.render", replacement)

    assert reason == "structured_function_replacement_applied"
    assert patched is not None
    assert "return value.upper()" in patched
    assert "return str(value)" in patched


def test_structured_replacement_rejects_signature_and_name_drift():
    source = "def resolve(value):\n    return value\n"

    assert "replacement_signature_mismatch" in replacement_shape_errors(
        "def resolve(value, extra):\n    return value\n", "main.py:resolve", source
    )
    assert "replacement_target_name_mismatch" in replacement_shape_errors(
        "def other(value):\n    return value\n", "main.py:resolve", source
    )
