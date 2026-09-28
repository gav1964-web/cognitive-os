"""Compatibility import; implementation lives in cognitive_inspect.commands."""
import sys
import cognitive_inspect.commands as _implementation

sys.modules[__name__] = _implementation
