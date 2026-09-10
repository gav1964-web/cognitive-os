"""Compatibility import; implementation lives in cognitive_replay.windows_job_process."""
import sys
import cognitive_replay.windows_job_process as _implementation

sys.modules[__name__] = _implementation
