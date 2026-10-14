"""Compatibility import; implementation lives in cognitive_inspect.structure.domain_anchors."""
import sys
import cognitive_inspect.structure.domain_anchors as _implementation

sys.modules[__name__] = _implementation
