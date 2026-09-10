"""Compatibility import; implementation lives in cognitive_replay.historical_defect_pytest_plugin."""
import sys
import cognitive_replay.historical_defect_pytest_plugin as _implementation

sys.modules[__name__] = _implementation
