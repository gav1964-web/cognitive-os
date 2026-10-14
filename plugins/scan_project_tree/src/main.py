"""Compatibility import; implementation lives in cognitive_inspect.tree."""
import sys
import cognitive_inspect.tree as _implementation

sys.modules[__name__] = _implementation
