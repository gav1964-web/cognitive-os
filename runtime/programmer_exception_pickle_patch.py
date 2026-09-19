"""Legacy import retained for external callers and compatibility regressions.

All working runtime consumers use exception_pickle_contract directly. Remove this
alias when downstream imports retire; it performs the same registry admission.
"""
from .exception_pickle_contract import (
    propose_exception_pickle_patch as exception_pickle_reconstruction_patch,
)

__all__ = ['exception_pickle_reconstruction_patch']
