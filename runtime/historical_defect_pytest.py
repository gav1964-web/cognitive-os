"""Compatibility import; implementation lives in cognitive_replay.pytest_report."""
import sys
import cognitive_replay.pytest_report as _implementation

sys.modules[__name__] = _implementation
