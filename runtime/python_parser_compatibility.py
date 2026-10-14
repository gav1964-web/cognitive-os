"""Compatibility import; implementation lives in cognitive_inspect.python_parser_compatibility."""
import sys
import cognitive_inspect.python_parser_compatibility as _implementation

sys.modules[__name__] = _implementation
