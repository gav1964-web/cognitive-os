"""Compatibility import; implementation lives in cognitive_inspect.structure.insights."""
import sys
import cognitive_inspect.structure.insights as _implementation

sys.modules[__name__] = _implementation
