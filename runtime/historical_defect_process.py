"""Compatibility import; implementation lives in cognitive_replay.process."""
import sys
import cognitive_replay.process as _implementation

sys.modules[__name__] = _implementation
