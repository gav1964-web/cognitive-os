"""Compatibility import; implementation lives in cognitive_inspect.structure.policy_candidates."""
import sys
import cognitive_inspect.structure.policy_candidates as _implementation

sys.modules[__name__] = _implementation
