"""Compatibility import; implementation lives in cognitive_replay.environment."""
import sys
import cognitive_replay.environment as _implementation

sys.modules[__name__] = _implementation
