"""Compatibility import; implementation lives in cognitive_inspect.python_source_files."""
import sys
import cognitive_inspect.python_source_files as _implementation

sys.modules[__name__] = _implementation
