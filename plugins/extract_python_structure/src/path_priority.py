"""Compatibility import; implementation lives in cognitive_inspect.structure.path_priority."""
import sys
import cognitive_inspect.structure.path_priority as _implementation

sys.modules[__name__] = _implementation
