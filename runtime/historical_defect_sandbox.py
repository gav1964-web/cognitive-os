"""Compatibility import; implementation lives in cognitive_replay.sandbox."""
import sys
import cognitive_replay.sandbox as _implementation

sys.modules[__name__] = _implementation
