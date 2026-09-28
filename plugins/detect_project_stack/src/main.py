"""Compatibility import; implementation lives in cognitive_inspect.stack."""
import sys
import cognitive_inspect.stack as _implementation

sys.modules[__name__] = _implementation
