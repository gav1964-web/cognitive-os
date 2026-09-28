"""Compatibility import; implementation lives in cognitive_inspect.structure.main."""
import sys
import cognitive_inspect.structure.main as _implementation

sys.modules[__name__] = _implementation
