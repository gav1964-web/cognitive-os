"""Compatibility import; implementation lives in cognitive_replay.setup_identity."""
import sys
import cognitive_replay.setup_identity as _implementation

sys.modules[__name__] = _implementation
